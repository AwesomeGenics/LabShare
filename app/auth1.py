from flask import Flask, redirect, url_for, session, request,flash, Blueprint, render_template
from app.db import check_existance, add_temporary
from werkzeug.security import check_password_hash, generate_password_hash


auth = Blueprint('auth', __name__)

@auth.route("/")
def home():
    if session.get("user_id"):
        return redirect("/dashboard")
    return redirect(url_for("auth.login"))


@auth.route("/login", methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        pwd = request.form.get('password')
        
        a = login_check(email)

        if a and check_password_hash(a['password'], pwd):
            session['user_id'] = email
            session.permanent = True

            return redirect('/dashboard')
        else: 
            flash('Wrong Password hai dalle')
            return redirect('/login')
    return render_template('login.html')


@auth.route('/regi_uni', methods=['GET','POST'])
def regi_uni():
    if request.method == 'POST':
        clg_name = request.form.get('college')
        uni_mail = request.form.get('unimail')

        check = check_existance(clg_name)
        
        if check:
            flash('Account already exists, Please Login!')
            return redirect('/login')
        
        try: 
            add_temporary(uni_mail, clg_name)
            return redirect('/otp/uni')

        except Exception as e:
            return render_template('error.html', code = e)
    return render_template('regis_uni.html')



@auth.route('/regi_stu', methods=['GET','POST'])
def regi_stu():
    if request.method == 'POST':
        std_name = request.form.get('name')
        std_mail = request.form.get('email')

        check = check_existance(std_name)
        
        if check:
            flash('Account already exists, Please Login!')
            return redirect('/login')
        
        try: 
            add_temporary(std_mail, std_name)
            return redirect('/otp/std')

        except Exception as e:
            return render_template('error.html', code = e)
    return render_template('regis_stu.html')


@auth.route('/reg_adm', methods=['GET','POST'])
def reg_adm():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        pwd = request.form.get('password')
        num = request.form.get('number')

        pwd_hash = generate_password_hash(pwd)
        add_user(email, pwd_hash, num)
        session['user_id'] = email
        return redirect('/dashboard')
    return render_template('create.html')


@auth.route('/otp/<type>', methods=['GET','POST'])
def otp(type):
    if request.method == 'POST':
        code = request.form.get('otp')

        if type == 'stu' and code == '0000':
            check_existance()
        elif type == 'uni':
            pass

    return render_template('otp.html')

@auth.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == "__main__":
    auth.run(debug=True)