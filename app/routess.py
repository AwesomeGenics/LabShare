from flask import Flask, redirect, url_for, session, request,flash, Blueprint, render_template

func = Blueprint('func', __name__)

@func.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')