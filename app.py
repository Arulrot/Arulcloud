from flask import Flask, render_template, request, redirect, session, url_for, send_file, jsonify, flash
import boto3
import os
import hmac
import hashlib
import base64
import pymysql
import json
from werkzeug.utils import secure_filename
from io import BytesIO
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

def load_config_from_secrets():
    secretsmanager = boto3.client('secretsmanager', region_name='ap-south-1')
    secret_value = secretsmanager.get_secret_value(SecretId='arulcloud-secconfig')
    return json.loads(secret_value['SecretString'])

config = load_config_from_secrets()

USER_POOL_ID = config['USER_POOL_ID']
CLIENT_ID = config['CLIENT_ID']
CLIENT_SECRET = config['CLIENT_SECRET']
REGION = config['REGION']
S3_BUCKET = config['S3_BUCKET']
RDS_HOST = config['RDS_HOST']
RDS_USER = config['RDS_USER']
RDS_PASSWORD = config['RDS_PASSWORD']
RDS_DB = config['RDS_DB']

s3 = boto3.client('s3', region_name=REGION)
cognito = boto3.client('cognito-idp', region_name=REGION)

def get_secret_hash(username):
    message = username + CLIENT_ID
    dig = hmac.new(
        bytes(CLIENT_SECRET, 'utf-8'),
        msg=bytes(message, 'utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

def get_db_connection(use_db=True):
    if use_db:
        return pymysql.connect(
            host=RDS_HOST,
            user=RDS_USER,
            password=RDS_PASSWORD,
            database=RDS_DB,
            connect_timeout=5
        )
    else:
        return pymysql.connect(
            host=RDS_HOST,
            user=RDS_USER,
            password=RDS_PASSWORD,
            connect_timeout=5
        )

def init_db():
    admin_conn = None
    try:
        admin_conn = get_db_connection(use_db=False)
        with admin_conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {RDS_DB}")
            admin_conn.commit()
    except Exception as e:
        return
    finally:
        if admin_conn:
            admin_conn.close()
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_plans (
                    email VARCHAR(255) PRIMARY KEY,
                    plan VARCHAR(20) NOT NULL DEFAULT 'free'
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    name VARCHAR(20) PRIMARY KEY,
                    storage_limit_mb INT NOT NULL
                )
            """)
            
            cursor.execute("""
                INSERT IGNORE INTO plans (name, storage_limit_mb) 
                VALUES 
                    ('free', 500),
                    ('silver', 600),
                    ('gold', 700),
                    ('premium', 800)
            """)
            
            conn.commit()
    except Exception as e:
        pass
    finally:
        if conn:
            conn.close()

def get_user_storage_limit(email):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.storage_limit_mb 
                FROM user_plans up
                JOIN plans p ON up.plan = p.name
                WHERE up.email = %s
            """, (email,))
            result = cursor.fetchone()
            return result[0] * 1024 * 1024 if result else 500 * 1024 * 1024
    except Exception as e:
        return 500 * 1024 * 1024
    finally:
        if conn:
            conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        try:
            cognito.sign_up(
                ClientId=CLIENT_ID,
                SecretHash=get_secret_hash(email),
                Username=email,
                Password=password,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name}
                ]
            )
            conn = None
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO user_plans (email, plan) VALUES (%s, 'free')", (email,))
                conn.commit()
            except Exception as e:
                pass
            finally:
                if conn:
                    conn.close()
                    
            return redirect(url_for('verify', email=email))
        except Exception as e:
            return render_template('register.html', error=str(e))
    return render_template('register.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = request.args.get('email')
    if request.method == 'POST':
        code = request.form['code']
        try:
            cognito.confirm_sign_up(
                ClientId=CLIENT_ID,
                SecretHash=get_secret_hash(email),
                Username=email,
                ConfirmationCode=code
            )
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('verify.html', email=email, error="Invalid or expired verification code.")
    return render_template('verify.html', email=email)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            auth_response = cognito.initiate_auth(
                ClientId=CLIENT_ID,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password,
                    'SECRET_HASH': get_secret_hash(email)
                }
            )
            session['user'] = email
            return redirect(url_for('main'))
        except Exception as e:
            return render_template('login.html', error="Invalid credentials or user not verified.")
    return render_template('login.html')

def get_user_storage_usage(email):
    paginator = s3.get_paginator('list_objects_v2')
    total = 0
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f'{email}/'):
        if 'Contents' in page:
            for obj in page['Contents']:
                if not obj['Key'].endswith('/'):
                    total += obj['Size']
    return total

@app.route('/main')
@login_required
def main():
    email = session['user']
    
    storage_limit = get_user_storage_limit(email)
    max_mb = storage_limit // (1024 * 1024)
    
    paginator = s3.get_paginator('list_objects_v2')
    files = []
    total_bytes = 0
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{email}/"):
        if 'Contents' in page:
            for obj in page['Contents']:
                if not obj['Key'].endswith('/'):
                    filename = obj['Key'].split('/')[-1]
                    if filename:
                        files.append(filename)
                        total_bytes += obj['Size']

    used_mb = round(total_bytes / (1024 * 1024), 2)
    usage_percent = min(100, round((total_bytes / storage_limit) * 100, 2))

    user_plan = 'free'
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT plan FROM user_plans WHERE email = %s", (email,))
            result = cursor.fetchone()
            user_plan = result[0] if result else 'free'
    except Exception as e:
        pass
    finally:
        if conn:
            conn.close()

    messages = []
    if '_flashes' in session:
        messages = [msg[1] for msg in session['_flashes']]
        session['_flashes'] = []

    return render_template(
        'main.html',
        user=email,
        files=files,
        used_mb=used_mb,
        usage_percent=usage_percent,
        max_mb=max_mb,
        user_plan=user_plan,
        messages=messages
    )

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    email = session['user']
    files = request.files.getlist('files')
    storage_limit = get_user_storage_limit(email)
    current_bytes = get_user_storage_usage(email)
    
    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if current_bytes + size > storage_limit:
            flash(f"Storage limit exceeded: {filename}", "error")
            continue

        try:
            s3.upload_fileobj(
                file,
                S3_BUCKET,
                f"{email}/{filename}"
            )
            current_bytes += size
            flash(f"Uploaded successfully: {filename}", "success")
        except Exception as e:
            flash(f"Error uploading {filename}: {str(e)}", "error")
            
    return redirect(url_for('main'))

@app.route('/rename', methods=['POST'])
@login_required
def rename_file():
    email = session['user']
    old_name = request.form['old_name']
    new_name = secure_filename(request.form['new_name'])

    if not new_name or '/' in new_name:
        flash("Invalid filename", "error")
        return redirect(url_for('main'))

    old_key = f"{email}/{old_name}"
    new_key = f"{email}/{new_name}"

    try:
        s3.copy_object(
            Bucket=S3_BUCKET,
            CopySource={'Bucket': S3_BUCKET, 'Key': old_key},
            Key=new_key
        )
        s3.delete_object(Bucket=S3_BUCKET, Key=old_key)
        flash(f"Renamed successfully: {old_name} → {new_name}", "success")
    except Exception as e:
        flash(f"Error renaming file: {str(e)}", "error")
    
    return redirect(url_for('main'))

@app.route('/preview/<filename>')
@login_required
def preview(filename):
    email = session['user']
    key = f"{email}/{filename}"
    
    try:
        file_obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return send_file(
            BytesIO(file_obj['Body'].read()),
            mimetype='application/octet-stream',
            as_attachment=False
        )
    except Exception as e:
        flash(f"Error previewing file: {str(e)}", "error")
        return redirect(url_for('main'))

@app.route('/download/<filename>')
@login_required
def download(filename):
    email = session['user']
    key = f"{email}/{filename}"
    
    try:
        file_obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return send_file(
            BytesIO(file_obj['Body'].read()),
            download_name=filename,
            as_attachment=True
        )
    except:
        flash("Error downloading file", "error")
        return redirect(url_for('main'))

@app.route('/delete/<filename>')
@login_required
def delete(filename):
    email = session['user']
    key = f"{email}/{filename}"
    
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=key)
        flash(f"Deleted successfully: {filename}", "success")
    except Exception as e:
        flash(f"Error deleting file: {str(e)}", "error")
    
    return redirect(url_for('main'))

@app.route('/upgrade_plan', methods=['POST'])
@login_required
def upgrade_plan():
    email = session['user']
    plan = request.form['plan']
    
    if plan not in ['free', 'silver', 'gold', 'premium']:
        flash("Invalid plan selected", "error")
        return redirect(url_for('main'))
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE user_plans SET plan = %s WHERE email = %s", (plan, email))
        conn.commit()
        flash(f"Plan upgraded to {plan} successfully!", "success")
    except Exception as e:
        flash(f"Error upgrading plan: {str(e)}", "error")
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('main'))

@app.route('/plans')
@login_required
def plans():
    email = session['user']
    
    user_plan = 'free'
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT plan FROM user_plans WHERE email = %s", (email,))
            result = cursor.fetchone()
            user_plan = result[0] if result else 'free'
    except Exception as e:
        pass
    finally:
        if conn:
            conn.close()
    
    return render_template('plans.html', user_plan=user_plan, user=email)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


init_db()