from flask import Flask, render_template, request, redirect, session, url_for
import boto3
import os
import hmac
import hashlib
import base64

app = Flask(__name__)
app.secret_key = os.urandom(24)

# AWS Cognito Configuration
USER_POOL_ID = 'ap-south-1_SAaG122HR'
CLIENT_ID = '67c891uh0llccmls153kh5870e'
CLIENT_SECRET = '1hnmo8rm5cjnkrt1n6e55h4deg5bc9i39nhfk0ftosb502av2dbi'
REGION = 'ap-south-1'

client = boto3.client('cognito-idp', region_name=REGION)

# Helper function to create SecretHash
def get_secret_hash(username):
    message = username + CLIENT_ID
    dig = hmac.new(
        bytes(CLIENT_SECRET, 'utf-8'),
        msg=bytes(message, 'utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

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
            client.sign_up(
                ClientId=CLIENT_ID,
                SecretHash=get_secret_hash(email),
                Username=email,
                Password=password,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name}
                ]
            )
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
            client.confirm_sign_up(
                ClientId=CLIENT_ID,
                SecretHash=get_secret_hash(email),
                Username=email,
                ConfirmationCode=code,
                ForceAliasCreation=False
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
            auth_response = client.initiate_auth(
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

@app.route('/main')
def main():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('main.html', user=session['user'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
