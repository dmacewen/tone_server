import sys
#sys.path.append('/home/dmacewen/Projects/colorMatch/service')
sys.path.append('/home/dmacewen/Projects/tone/tone_colorMatch/src/')

from flask import request, abort, jsonify
from werkzeug import secure_filename
from app import app as webApp
import runSteps
import cv2
import os
import stat
import psycopg2
from random import *

#IMAGES_DIR = '/home/dmacewen/Projects/colorMatch/images/'
IMAGES_DIR = '/home/dmacewen/Projects/tone/images/'

#CALIBRATIONS_DIR = '/home/dmacewen/Projects/colorMatch/calibrations/'
#CALIBRATION_CAPTURE_COUNT = 16

try:
    #Do not love storing password in plain text in code....
    conn = psycopg2.connect(dbname="tone",
                            user="postgres",
                            port="5434",
                            password="dirty vent unroof")

except (Exception, psycopg2.Error) as error:
    print("Error while fetch data from Postrgesql", error)
#finally:
#    if conn:
#        cursor.close()
#        connection.close()
#        print("Postgres Connection Closed")

def getAndUpdateUserImageCount(userName):
    print('Getting And Update User Image Count')
    #Save state like a dangus
    userImageCount = 0
    newLines = []
    #filePath = '/home/dmacewen/Projects/colorMatch/server/user_image_counter.txt';
    filePath = IMAGES_DIR + userName + '/image_counter.txt'

    imageCountFileExists = True
    if not os.path.exists(filePath):
        imageCountFileExists = False
        

    with open(filePath, 'r+') as f:
        lines = f.readlines() #Should only be one value in file, the number of photos taken
        if len(lines) != 0:
            userImageCount = int(lines[0])

        userImageCount = userImageCount + 1
        f.seek(0)
        f.write(str(userImageCount))
        f.truncate()

    if not imageCountFileExists:
        os.chmod(filePath, 0o777)

    return str(userImageCount)

def isUserTokenValid(user_id, request, check_awknowledged_nda=True):
    # Does user_id exist?
    print('Validating User ID :: {}'.format(user_id))

    try:
        user_id = int(user_id)
    except ValueError:
        return False

    getUserTokenQuery = 'SELECT token FROM users WHERE user_id=(%s)'
    data = (user_id, )

    with conn.cursor() as cursor:
        cursor.execute(getUserTokenQuery, data)
        userToken = cursor.fetchone()

    print('Stored Token {}'.format(userToken))

    token_key = 'token'
    if token_key not in request.args:
        return False

    recieved_token = request.args[token_key]

    try:
        recieved_token = int(recieved_token)
    except ValueError:
        return False

    print('Received user {} with token {}'.format(user_id, recieved_token))

    stored_token = userToken[0]

    print('Received vs Stored :: {} vs {}'.format(recieved_token, stored_token))

    if recieved_token != stored_token:
        return False

    print('Token is valid!')
    
    # Check is token valid

    #if checkBetaNDA:
        # Is Beta User? Is Confidentiality Awknowledged?
        # SELECT * FROM beta_users WHERE user_id == user_id
    if check_awknowledged_nda:
        getUserAcknowledgementQuery = 'SELECT acknowledge_confidentiality FROM beta_testers WHERE user_id=(%s)'
        data = (user_id, )

        with conn.cursor() as cursor:
            cursor.execute(getUserAcknowledgementQuery, data)
            userAcknowledgement = cursor.fetchone()

        print('User Awknowledged? :: {}'.format(userAcknowledgement))

        if userAcknowledgement is None:
            return False

        userAcknowledgement = userAcknowledgement[0]

        if not userAcknowledgement:
            return False



    return True

def isCaptureSessionValid(user_id, session_id):
    return False

@webApp.route('/')
@webApp.route('/index')
def index():
    return webApp.send_static_file('index.html')

@webApp.route('/users', methods=['POST'])
def users():
    if request.method == 'POST':
        print('GOT LOGIN REQUEST')
        print(request.form)
        email_key = 'email'
        password_key = 'password'

        if email_key not in request.form:
            abort(403)

        email = request.form[email_key]

        if password_key not in request.form:
            abort(403)

        password = request.form[password_key]


        # Connect to database
        # Get full user
        # Check that password matched
        # If beta user, dont issue token until user signs nda
        # If yes, return user_id and Generate Token. Store token and send to user
        # If no, abort 403
        
        getUserQuery = 'SELECT user_id, pass FROM users WHERE email=(%s)'
        data = (email, )

        with conn.cursor() as cursor:
            cursor.execute(getUserQuery, data)
            user = cursor.fetchone()

        print("Got user {}".format(user))

        isAuthentic = (user is not None) and (user[1] == password)

        if not isAuthentic:
            abort(403)

        user_id = user[0]
        sudo_random_token = int(2147483647 * random())

        updateUserTokenQuery = 'UPDATE users SET token=(%s) WHERE user_id=(%s)'
        data = (sudo_random_token, user_id)

        with conn.cursor() as cursor:
            cursor.execute(updateUserTokenQuery, data)
            conn.commit()

        response = {}
        response['user_id'] = user_id
        response['token'] = sudo_random_token

        return jsonify(response)
        #return 'Recieved user {} with pass {} | Authentic :: {} | token :: {}'.format(email, password, isAuthentic, sudo_random_token)

    abort(404)

@webApp.route('/users/<user_id>', methods=['GET'])
def user(user_id):
    if request.method == 'GET':

        if not isUserTokenValid(user_id, request):
            abort(403)

        getUserSettingsQuery = 'SELECT settings FROM user_settings WHERE user_id=(%s)'
        data = (user_id, )

        with conn.cursor() as cursor:
            cursor.execute(getUserSettingsQuery, data)
            user_settings = cursor.fetchone()

        print('Got User ({}) Settings {}'.format(user_id, user_settings))

        if user_settings is None:
            return jsonify({})

        return user_settings

        # Connect to database
        # Return user settings and if beta user

    abort(404)

@webApp.route('/users/<user_id>/agree', methods=['PUT'])
def user_agreement(user_id):
    if request.method == 'PUT':

        if not isUserTokenValid(user_id, request, False):
            abort(403)

        
        agreement_key = 'agree'
        if agreement_key not in request.form:
            abort(403)

        agreement = request.form[agreement_key].lower()

        print('AGREEMENT :: {}'.format(agreement))



        isTrue = agreement == 'true'
        isFalse = agreement == 'false'

        if (not isTrue) and (not isFalse):
            abort(403)

        agreement = isTrue

        if agreement:
            print('Passes True')

        if not agreement:
            print('Passes False')

        print('AGREEMENT :: {}'.format(agreement))

        updateUserAwknoledgement = 'INSERT INTO beta_testers (user_id, acknowledge_confidentiality) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET (acknowledge_confidentiality)=ROW(EXCLUDED.acknowledge_confidentiality)'
        data = (user_id, agreement)

        with conn.cursor() as cursor:
            cursor.execute(updateUserAwknoledgement, data)
            conn.commit()

        if not agreement:
            abort(403)

        return "Received"

        # Connect to database
        # Set agree to true

    abort(404)

@webApp.route('/users/<user_id>/session', methods=['GET', 'POST'])
def user_capture_session(user_id):
    if not isUserTokenValid(user_id, request):
        abort(403)
    
    if request.method == 'POST':
        skin_color_id_key = 'skin_color_id'

        if skin_color_id_key not in request.form:
            abort(403)

        skin_color_id = request.form[skin_color_id_key]

        try:
            skin_color_id = int(skin_color_id)
        except ValueError:
            abort(403)

        print('Skin Color Id :: {}'.format(skin_color_id))

        insertNewSessionQuery = 'INSERT INTO capture_sessions (user_id, skin_color_id, out_of_date) VALUES (%s, %s, %s)'
        data = (user_id, skin_color_id, False)

        with conn.cursor() as cursor:
            cursor.execute(insertNewSessionQuery, data)
            conn.commit()
        
        # Save updated session info in db

    # GET and POST both return same info

    # Return session id
    # Return skin color id
    # Return start database
    # Return number of captures in this session
    getCurrentCaptureSession = 'SELECT session_id, skin_color_id, start_date, out_of_date FROM capture_sessions WHERE user_id=(%s) AND start_date = (SELECT max(start_date) FROM capture_sessions WHERE user_id=(%s))'
    data = (user_id, user_id)

    with conn.cursor() as cursor:
        cursor.execute(getCurrentCaptureSession, data)
        currentUserSession = cursor.fetchone()

    if currentUserSession is None:
        print('No user capture session found')
        abort(404)

    currentUserSessionObj = {}
    currentUserSessionObj['session_id'] = currentUserSession[0]
    currentUserSessionObj['skin_color_id'] = currentUserSession[1]
    currentUserSessionObj['start_date'] = currentUserSession[2]
    currentUserSessionObj['out_of_date'] = currentUserSession[3]

    return jsonify(currentUserSessionObj)

@webApp.route('/users/<user_id>/capture', methods=['POST'])
def user_capture(user_id):

    if request.method == 'POST':

        if not isUserTokenValid(user_id, request):
            abort(403)

        #if not os.path.exists(IMAGES_DIR + '/' + user_id):
        #    return "User " + user_id + " does not exist!"

        # Unpack data
        # Store metadata
        # save metadata file and capture data in FS
        # save paths to data in DB

        metadata = None
        images = []
        fileNames = [key for key in request.files.keys()]
        print('FILE NAMES :: ' + str(fileNames))
        for fileName in fileNames:
            if fileName == 'metadata':
                metadata = request.files[fileName]
            else:
                images.append([fileName, request.files[fileName]])
                

        userImageCount = getAndUpdateUserImageCount(user_id)
        userImageSetName = secure_filename(user_id + userImageCount)

        dirPath = IMAGES_DIR + '/' + user_id + '/' + userImageSetName + '/'

        if not os.path.exists(dirPath):
            os.mkdir(dirPath)

        os.chmod(dirPath, 0o777)

        for imageName, image in images:
            imagePath = dirPath + userImageSetName + '-' + imageName + '.PNG'
            image.save(imagePath)
            os.chmod(imagePath, 0o777)

        metadataPath = dirPath + userImageSetName + '-metadata.txt'
        print("METADATA PATH :: " + metadataPath)
        metadata.save(metadataPath)
        print("Metadata Saved")
        os.chmod(metadataPath, 0o777)
        print("Metadata Access Changed")

        try:
            colorAndFluxish = runSteps.run(user_id, userImageSetName);
        except Exception as e:
            print("Error :: " + str(e))
            return str(e)
        except:
            return 'And Unknown error occured'
        else:
            print("Success")
            return jsonify(colorAndFluxish)

    abort(404)
