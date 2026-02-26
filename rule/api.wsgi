# version=3.7.1
# vim: syntax=python
import sys, os

os.environ['FLASK_ENV'] = 'prd'

activate_this = '/home/iavest/apps_wsgi/api/virtual_env/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

sys.path.append('/home/iavest/apps_wsgi/api')
from app import app as application