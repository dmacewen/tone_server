from flask import Flask

application = Flask(__name__, static_url_path='/static')

from application import routes

if __name__=="__main__":
    application.run(host='0.0.0.0')
