from flask import Flask, request, session, redirect, render_template, flash, Response,send_file
from flaskthreads import AppContextThread
from big import BigCommerceAuto,Logs
from wsgiref.simple_server import make_server
import os
from datetime import datetime

app=Flask(__name__)
app.config.from_object('config')

posts=[]

@app.route('/',methods=['GET','POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html',posts=Logs.get_log())
    if request.method == 'POST':
        try:
            os.remove('logs/last.log')
        except:
            pass
        selected=request.form.getlist('category')
        selected=True if selected else False
        t=AppContextThread(target=products,args=(selected,))
        t.start()
        return render_template('index.html')


def products(category_bool):
    #ovde dodaj client_id , token , store_hash
    Logs.log('NEW ENTRY\n{}'.format(datetime.today().strftime('%d.%h %Y %H:%M:%S')))    
    x=BigCommerceAuto()
    if category_bool == True:
        x.import_big_categories()
        sleep(5)
    x.import_big_products()
    Logs.log("FINISHED\n{}".format(datetime.today().strftime('%d.%h %Y %H:%M:%S')))

        
@app.route('/logs',methods=["GET"])
def logs():
    try:
        return send_file('logs/last.log')
    except FileNotFoundError:
        return ""

