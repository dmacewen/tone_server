#import sys
#sys.path.append('/home/dmacewen/Projects/colorMatch/service')
#sys.path.append('/home/dmacewen/Projects/tone/tone_colorMatch/src/')

from flask import request, abort, jsonify
from werkzeug import secure_filename
from werkzeug.datastructures import FileStorage
from application import application as webApp
#import runSteps
#import cv2
import os #Eventually replace by saving to s3
#import stat
import psycopg2 #Update to point to AWS RDS
from random import *
import json
import boto3
from application.logger import getLogger

#IMAGES_DIR = '/home/dmacewen/Projects/colorMatch/images/'
IMAGES_DIR = '/home/dmacewen/Projects/tone/images/'
TONE_USER_CAPTURES_BUCKET = 'tone-user-captures'
s3_client = boto3.client('s3', 'us-west-2')
sqs_resource = boto3.resource('sqs', 'us-west-2')
sqs_queue = sqs_resource.Queue('https://sqs.us-west-2.amazonaws.com/751119984625/awseb-e-qmun67ugcv-stack-AWSEBWorkerQueue-94V16AVJXYBL')
logger = getLogger(__name__)

try:
    if 'RDS_HOSTNAME' in os.environ:
        conn = psycopg2.connect(dbname=os.environ['RDS_DB_NAME'],
                                user=os.environ['RDS_USERNAME'],
                                password=os.environ['RDS_PASSWORD'],
                                host=os.environ['RDS_HOSTNAME'],
                                port=os.environ['RDS_PORT'])

except (Exception, psycopg2.Error) as error:
    logger.error("Error while fetch data from Postrgesql ::\n{}".format(error))

def isUserTokenValid(user_id, request, check_awknowledged_nda=True):
    logger.info('Validating User ID :: {}'.format(user_id))

    try:
        user_id = int(user_id)
    except ValueError:
        logger.warning('User Authentication: Could not convert user_id to int')
        return False

    getUserTokenQuery = 'SELECT token FROM users WHERE user_id=(%s)'
    data = (user_id, )

    with conn.cursor() as cursor:
        cursor.execute(getUserTokenQuery, data)
        userToken = cursor.fetchone()

    token_key = 'token'
    if token_key not in request.args:
        logger.warning('User Authentication: token_key not in request args')
        return False

    recieved_token = request.args[token_key]

    try:
        recieved_token = int(recieved_token)
    except ValueError:
        logger.warning('User Authentication: Could not convert recieved_token to int')
        return False

    stored_token = userToken[0]

    logger.info('Received vs Stored :: {} vs {}'.format(recieved_token, stored_token))

    if recieved_token != stored_token:
        logger.info('Token is not valid!')
        return False

    logger.info('Token is valid!')
    
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

        if userAcknowledgement is None:
            logger.info('User Authentication: User has not acknowledge confidentiality')
            return False

        userAcknowledgement = userAcknowledgement[0]

        if not userAcknowledgement:
            logger.info('User Authentication: User did not agree to confidentiality')
            return False

    return True

def isCaptureSessionValid(user_id, session_id):
    return False

@webApp.route('/')
@webApp.route('/index')
def index():
    logger.info('Getting Root')
    return webApp.send_static_file('index.html')

#https://developer.apple.com/documentation/security/password_autofill/setting_up_an_app_s_associated_domains
@webApp.route('/apple-app-site-association')
def apple_app_site_association():
    logger.info('Getting apple web credientials')
    return webApp.send_static_file('apple-app-site-association')

@webApp.route('/users', methods=['POST'])
def users():
    if request.method == 'POST':
        logger.info('Got login request')
        email_key = 'email'
        password_key = 'password'

        if email_key not in request.form:
            logger.warning('Login: Email key not in request form')
            abort(403)

        email = request.form[email_key]

        if password_key not in request.form:
            logger.warning('Login: Password key not in request form')
            abort(403)

        password = request.form[password_key]
        
        getUserQuery = 'SELECT user_id, pass FROM users WHERE email=(%s)'
        data = (email, )

        with conn.cursor() as cursor:
            cursor.execute(getUserQuery, data)
            user = cursor.fetchone()

        isAuthentic = (user is not None) and (user[1] == password)

        if not isAuthentic:
            logger.warning('Login: User is not authentic')
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

    logger.warning('No matching Request Method in \'/users\' for {}'.format(request.method))
    abort(404)

@webApp.route('/users/<user_id>', methods=['GET', 'POST'])
def user(user_id):
    if not isUserTokenValid(user_id, request, False):
        logger.warning('User Not Valid :: user_id: {}'.format(user_id))
        abort(403)

    if request.method == 'GET':
        logger.info('Getting user settings for user_id {}'.format(user_id))
        getUserSettingsQuery = 'SELECT settings FROM user_settings WHERE user_id=(%s)'
        data = (user_id, )

        with conn.cursor() as cursor:
            cursor.execute(getUserSettingsQuery, data)
            possible_user_settings = cursor.fetchone()

            if possible_user_settings is None:
                user_settings = None
            else:
                user_settings = possible_user_settings[0]

        if user_settings is None:
            logger.info('Settings: No user settings for user_id :: {}'.format(user_id))
            return jsonify({})

        return jsonify(user_settings)

        # Connect to database
        # Return user settings and if beta user
    
    if request.method == 'POST':
        logger.info('Updating user settings for user_id {}'.format(user_id))
        settings_key = 'settings'
        if settings_key not in request.form:
            logger.warning('Settings: settings_key not found in request form')
            abort(403)

        settings = request.form[settings_key]

        try:
            settings = json.loads(settings)
        except ValueError:
            logger.warning('Settings: Could not load settings JSON')
            abort(403)

        updateUserSettingsQuery = 'INSERT INTO user_settings (user_id, settings) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET (settings)=ROW(EXCLUDED.settings)'
        data = (user_id, json.dumps(settings))

        with conn.cursor() as cursor:
            cursor.execute(updateUserSettingsQuery, data)
            conn.commit()

        return 'Success'

    logger.warning('No matching Request Method in \'/users/{}\' for {}'.format(user_id, request.method))
    abort(404)

@webApp.route('/users/<user_id>/agree', methods=['PUT'])
def user_agreement(user_id):
    if request.method == 'PUT':
        logger.info('Updating User Agreement')

        if not isUserTokenValid(user_id, request, False):
            logger.warning('User Not Valid :: user_id: {}'.format(user_id))
            abort(403)

        
        agreement_key = 'agree'
        if agreement_key not in request.form:
            logger.warning('User Agreement: agreement_key not found in request form')
            abort(403)

        agreement = request.form[agreement_key].lower()

        isTrue = ((agreement == 'true') or (agreement == "1"))
        isFalse = ((agreement == 'false') or (agreement == "0"))

        if (not isTrue) and (not isFalse):
            logger.warning('User Agreement: Could not convert Boolean')
            abort(403)

        agreement = isTrue

        updateUserAwknoledgement = 'INSERT INTO beta_testers (user_id, acknowledge_confidentiality) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET (acknowledge_confidentiality)=ROW(EXCLUDED.acknowledge_confidentiality)'
        data = (user_id, agreement)

        with conn.cursor() as cursor:
            cursor.execute(updateUserAwknoledgement, data)
            conn.commit()

        if not agreement:
            logger.info('User did not agree to agreement, user_id :: {}'.format(user_id))
            abort(403)

        return "Received"

    logger.warning('No matching Request Method in \'/users/{}/agree\' for {}'.format(user_id, request.method))
    abort(404)

@webApp.route('/users/<user_id>/session', methods=['GET', 'POST'])
def user_capture_session(user_id):
    if not isUserTokenValid(user_id, request, False):
        logger.warning('User Not Valid :: user_id: {}'.format(user_id))
        abort(403)
    
    if request.method == 'POST':
        logger.info('Creating new capture session for user_id :: {}'.format(user_id))
        skin_color_id_key = 'skin_color_id'

        if skin_color_id_key not in request.form:
            logger.warning('Capture Session: skin_color_id_key not found in request form')
            abort(403)

        skin_color_id = request.form[skin_color_id_key]

        try:
            skin_color_id = int(skin_color_id)
        except ValueError:
            logger.warning('Capture Session: Could not convert skin_color_id to int')
            abort(403)

        insertNewSessionQuery = 'INSERT INTO capture_sessions (user_id, skin_color_id, out_of_date) VALUES (%s, %s, %s)'
        data = (user_id, skin_color_id, False)

        with conn.cursor() as cursor:
            cursor.execute(insertNewSessionQuery, data)
            conn.commit()
        
        # Save updated session info in db

    # GET and POST both return same info

    getCurrentCaptureSession = 'SELECT session_id, skin_color_id, start_date, out_of_date, NOW()::TIMESTAMP FROM capture_sessions WHERE user_id=(%s) AND start_date = (SELECT max(start_date) FROM capture_sessions WHERE user_id=(%s))'
    data = (user_id, user_id)

    with conn.cursor() as cursor:
        cursor.execute(getCurrentCaptureSession, data)
        currentUserSession = cursor.fetchone()

    if currentUserSession is None:
        currentUserSessionObj = {}
        currentUserSessionObj['session_id'] = 0
        currentUserSessionObj['skin_color_id'] = 0
        currentUserSessionObj['start_date'] = '2019-06-06 22:51:25.080722'
        currentUserSessionObj['out_of_date'] = True
        currentUserSessionObj['now'] = '2019-06-06 22:51:25.080722'
        return jsonify(currentUserSessionObj)

    #return jsonify(currentUserSessionObj)
    #    logger.warning('Capture Session: No user capture session found for user_id {}'.format(user_id))
    #    abort(404)

    currentUserSessionObj = {}
    currentUserSessionObj['session_id'] = currentUserSession[0]
    currentUserSessionObj['skin_color_id'] = currentUserSession[1]
    currentUserSessionObj['start_date'] = str(currentUserSession[2]) #Convert dates to strings so jsonify doesnt mess with them
    currentUserSessionObj['out_of_date'] = currentUserSession[3]
    currentUserSessionObj['now'] = str(currentUserSession[4])

    return jsonify(currentUserSessionObj)

@webApp.route('/users/<user_id>/capture', methods=['POST'])
def user_capture(user_id):

    if request.method == 'POST':
        logger.info('Received new user capture')

        if not isUserTokenValid(user_id, request):
            logger.warning('User Not Valid :: user_id: {}'.format(user_id))
            abort(403)

        images = []
        parameters = None
        fileNames = [key for key in request.files.keys()]
        
        #Fetch Parameters here because they are passed in a file. Apparently multipart file uploads dont support parametes??
        for fileName in fileNames:
            if fileName == 'parameters':
                parameters = request.files[fileName]
            else:
                images.append([fileName, request.files[fileName]])

        try:
            parameters = json.loads(parameters.read())
        except ValueError:
            logger.warning('Capture: Could not load parameters JSON')
            abort(403)

        if not images:
            logger.warning('Capture: No images in request')
            abort(403)

        # PASSED IN:     user_id | session_id | app_version | device_info
        # FILES:    capture_metadata | capture_data
        # GENERATE: capture_id | capture_date | capture_path 

        session_id_key = 'session_id'
        app_version_key = 'app_version'
        device_info_key = 'device_info'
        metadata_key = 'metadata'

        if session_id_key not in parameters:
            logger.warning('Capture: session_id_key not in parameters')
            abort(403)

        session_id = parameters[session_id_key]

        try:
            session_id = int(session_id)
        except ValueError:
            logger.warning('Capture: Could not convert session_id to int')
            abort(403)

        #Check that it is the most recent session... Or at least that session exists?
        captureSessionQuery = 'SELECT skin_color_id, start_date, out_of_date FROM capture_sessions WHERE session_id=(%s) AND user_id=(%s)'
        data = (session_id, user_id)

        with conn.cursor() as cursor:
            cursor.execute(captureSessionQuery, data)
            sessionData = cursor.fetchone()

        if sessionData is None:
            logger.warning('Capture: could not find capture session for user_id {}'.format(user_id))
            abort(403)

        if app_version_key not in parameters:
            logger.warning('Capture: app_version_key not in parameters')
            abort(403)

        app_version = parameters[app_version_key]

        if device_info_key not in parameters:
            logger.warning('Capture: device_info_key not in parameters')
            abort(403)

        device_info = parameters[device_info_key]

        try:
            device_info = json.loads(device_info)
        except ValueError:
            logger.warning('Capture: Could not load device info JSON')
            abort(403)

        if metadata_key not in parameters:
            logger.warning('Capture: metadata_key not in parameters')
            abort(403)

        metadata = parameters[metadata_key]

        try:
            metadata = json.loads(metadata)
        except ValueError:
            logger.warning('Capture: Could not load metadata JSON')
            abort(403)

        # /<user_id>/<sessoin_id>/<capture_id>/[1-8, 1-8_[left, right]Eye, metadata].[PNG, JSON]

        insertNewCaptureQuery = 'INSERT INTO captures (session_id, user_id, app_version, device_info, capture_metadata) VALUES (%s, %s, %s, %s, %s) RETURNING capture_id'
        data = (session_id, user_id, app_version, json.dumps(device_info), json.dumps(metadata))

        with conn.cursor() as cursor:
            cursor.execute(insertNewCaptureQuery, data)
            capture_id = cursor.fetchone()[0]
            conn.commit()

        userSessionCapturePath = '{}/{}/{}'.format(str(user_id), str(session_id), str(capture_id))

        logger.info('Capture: Saving data to S3 path tone-user-captures::{}'.format(userSessionCapturePath))
        for imageName, image in images:
            secureImageName = secure_filename(imageName + '.png')
            imagePath = '{}/{}'.format(userSessionCapturePath, secureImageName)
            s3_client.put_object(Bucket=TONE_USER_CAPTURES_BUCKET, Key=imagePath, Body=image)

        metadataPath = '{}/{}'.format(userSessionCapturePath, 'metadata.json')
        s3_client.put_object(Bucket=TONE_USER_CAPTURES_BUCKET, Key=metadataPath, Body=json.dumps(metadata))

        try:
            #colorAndFluxish = runSteps.run(user_id, userImageSetName);
            #colorAndFluxish = runSteps.run2(user_id);
            logger.info('Capture: Added Task to SQS :: (user_id, session_id, capture_id) : ({}, {}, {})'.format(user_id, session_id, capture_id))
            #colorAndFluxish = {}
            #colorAndFluxish["todo"] = "add task to sqs"
            colorMatchMessage = {}
            colorMatchMessage['user_id'] = user_id
            colorMatchMessage['session_id'] = session_id
            colorMatchMessage['capture_id'] = capture_id
            colorMatchMessageJson = json.dumps(colorMatchMessage)
            queue_response = sqs_queue.send_message(MessageBody=colorMatchMessageJson)
            logger.info('Capture: SQS Response :: {}'.format(queue_response))
        except Exception as e:
            logger.error('Capture: Error adding task to SQS for (user_id, session_id, capture_id) : ({}, {}, {})\n{}'.format(user_id, session_id, capture_id, e))
            return str(e)
        except:
            logger.error('Capture: Error adding task to SQS for (user_id, session_id, capture_id) : ({}, {}, {})'.format(user_id, session_id, capture_id))
            return 'And Unknown error occured'
        else:
            logger.info('Capture: Success (user_id, session_id, capture_id) : ({}, {}, {})'.format(user_id, session_id, capture_id))
            return colorMatchMessageJson

    logger.warning('No matching Request Method in \'/users/{}/capture\' for {}'.format(user_id, request.method))
    abort(404)
