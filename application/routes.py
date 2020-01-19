"""
Defines the routes and handlers for the Tone server
"""
import os
import json
from random import random
from flask import request, abort, jsonify
from werkzeug import secure_filename
import psycopg2
import boto3
from application import application as webApp
from application.logger import getLogger
LOGGER = getLogger(__name__)

TONE_USER_CAPTURES_BUCKET = 'tone-user-captures'

s3_client = boto3.client('s3', 'us-west-2')
sqs_resource = boto3.resource('sqs', 'us-west-2')
sqs_queue = sqs_resource.Queue('https://sqs.us-west-2.amazonaws.com/751119984625/awseb-e-qmun67ugcv-stack-AWSEBWorkerQueue-IDEJOD7KLNEV')

try:
    if 'RDS_HOSTNAME' in os.environ:
        conn = psycopg2.connect(dbname=os.environ['RDS_DB_NAME'],
                                user=os.environ['RDS_USERNAME'],
                                password=os.environ['RDS_PASSWORD'],
                                host=os.environ['RDS_HOSTNAME'],
                                port=os.environ['RDS_PORT'])

except psycopg2.Error as error:
    LOGGER.error("Error while fetch data from Postrgesql ::\n%s", error)

def isUserTokenValid(user_id, user_request, check_acknowledged_nda=True):
    """
    Checks whether the user token is valid, returns TRUE if it is, FALSE otherwise
        NOTE: options to check acknowledged nda. If it should check, function retuns TRUE if nda is acknowledged, FALSE otherwise
    """
    LOGGER.info('Validating User ID :: %s', user_id)

    try:
        user_id = int(user_id)
    except ValueError:
        LOGGER.warning('User Authentication: Could not convert user_id to int')
        return False

    getUserTokenQuery = 'SELECT token FROM users WHERE user_id=(%s)'
    data = (user_id, )

    with conn.cursor() as cursor:
        cursor.execute(getUserTokenQuery, data)
        userToken = cursor.fetchone()

    token_key = 'token'
    if token_key not in user_request.args:
        LOGGER.warning('User Authentication: Token key not in user_request args')
        return False

    recieved_token = user_request.args[token_key]

    try:
        recieved_token = int(recieved_token)
    except ValueError:
        LOGGER.warning('User Authentication: Could not convert recieved_token to int')
        return False

    stored_token = userToken[0]

    LOGGER.info('Received vs Stored :: %s vs %s', recieved_token, stored_token)

    if recieved_token != stored_token:
        LOGGER.info('Token is not valid!')
        return False

    LOGGER.info('Token is valid!')

    if check_acknowledged_nda:
        getUserAcknowledgementQuery = 'SELECT acknowledge_confidentiality FROM beta_testers WHERE user_id=(%s)'
        data = (user_id, )

        with conn.cursor() as cursor:
            cursor.execute(getUserAcknowledgementQuery, data)
            userAcknowledgement = cursor.fetchone()

        if userAcknowledgement is None:
            LOGGER.info('User Authentication: User has not acknowledge confidentiality')
            return False

        userAcknowledgement = userAcknowledgement[0]

        if not userAcknowledgement:
            LOGGER.info('User Authentication: User did not agree to confidentiality')
            return False

    return True

@webApp.route('/')
@webApp.route('/index')
def index():
    """Returnsindex.html"""
    LOGGER.info('Getting Root')
    return webApp.send_static_file('index.html')

#https://developer.apple.com/documentation/security/password_autofill/setting_up_an_app_s_associated_domains
@webApp.route('/apple-app-site-association')
def apple_app_site_association():
    """Return apple app site association - Apple security measure for password autofill"""
    LOGGER.info('Getting apple web credientials')
    return webApp.send_static_file('apple-app-site-association')

@webApp.route('/users', methods=['POST'])
def users():
    """Update user"""
    if request.method == 'POST':
        LOGGER.info('Got login request')
        email_key = 'email'
        password_key = 'password'

        if email_key not in request.form:
            LOGGER.warning('Login: Email key not in request form')
            abort(403)

        email = request.form[email_key]

        if password_key not in request.form:
            LOGGER.warning('Login: Password key not in request form')
            abort(403)

        password = request.form[password_key]

        getUserQuery = 'SELECT user_id, pass FROM users WHERE email=(%s)'
        data = (email, )

        with conn.cursor() as cursor:
            cursor.execute(getUserQuery, data)
            user = cursor.fetchone()

        isAuthentic = (user is not None) and (user[1] == password)

        if not isAuthentic:
            LOGGER.warning('Login: User is not authentic')
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

    LOGGER.warning('No matching Request Method in \'/users\' for %s', request.method)
    abort(404)
    return None

@webApp.route('/users/<user_id>', methods=['GET', 'POST'])
def user(user_id):
    """Updates user settings"""
    if not isUserTokenValid(user_id, request, False):
        LOGGER.warning('User Not Valid :: user_id: %s', user_id)
        abort(403)

    if request.method == 'GET':
        LOGGER.info('Getting user settings for user_id %s', user_id)
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
            LOGGER.info('Settings: No user settings for user_id :: %s', user_id)
            return jsonify({})

        return jsonify(user_settings)

    if request.method == 'POST':
        LOGGER.info('Updating user settings for user_id %s', user_id)
        settings_key = 'settings'
        if settings_key not in request.form:
            LOGGER.warning('Settings: settings_key not found in request form')
            abort(403)

        settings = request.form[settings_key]

        try:
            settings = json.loads(settings)
        except ValueError:
            LOGGER.warning('Settings: Could not load settings JSON')
            abort(403)

        updateUserSettingsQuery = ('INSERT INTO user_settings (user_id, settings)',
                                   'VALUES (%s, %s)',
                                   'ON CONFLICT (user_id)'
                                   'DO UPDATE SET (settings)=ROW(EXCLUDED.settings)')

        data = (user_id, json.dumps(settings))

        with conn.cursor() as cursor:
            cursor.execute(updateUserSettingsQuery, data)
            conn.commit()

        return 'Success'

    LOGGER.warning('No matching Request Method in \'/users/%s\' for %s', user_id, request.method)
    abort(404)
    return None

@webApp.route('/users/<user_id>/agree', methods=['PUT'])
def user_agreement(user_id):
    """Updates user agreement"""
    if request.method == 'PUT':
        LOGGER.info('Updating User Agreement')

        if not isUserTokenValid(user_id, request, False):
            LOGGER.warning('User Not Valid :: user_id: %s', user_id)
            abort(403)

        agreement_key = 'agree'
        if agreement_key not in request.form:
            LOGGER.warning('User Agreement: agreement_key not found in request form')
            abort(403)

        agreement = request.form[agreement_key].lower()

        isTrue = agreement in ('true', '1')
        isFalse = agreement in ('false', '0')

        if (not isTrue) and (not isFalse):
            LOGGER.warning('User Agreement: Could not convert Boolean')
            abort(403)

        agreement = isTrue

        updateUserAwknoledgement = ('INSERT INTO beta_testers (user_id, acknowledge_confidentiality)',
                                    'VALUES (%s, %s)',
                                    'ON CONFLICT (user_id)'
                                    'DO UPDATE SET (acknowledge_confidentiality)=ROW(EXCLUDED.acknowledge_confidentiality)')
        data = (user_id, agreement)

        with conn.cursor() as cursor:
            cursor.execute(updateUserAwknoledgement, data)
            conn.commit()

        if not agreement:
            LOGGER.info('User did not agree to agreement, user_id :: %s', user_id)
            abort(403)

        return "Received"

    LOGGER.warning('No matching Request Method in \'/users/%s/agree\' for %s', user_id, request.method)
    abort(404)
    return None

@webApp.route('/users/<user_id>/session', methods=['GET', 'POST'])
def user_capture_session(user_id):
    """Returns or updates the user's capture session"""
    if not isUserTokenValid(user_id, request, False):
        LOGGER.warning('User Not Valid :: user_id: %s', user_id)
        abort(403)

    if request.method == 'POST':
        LOGGER.info('Creating new capture session for user_id :: %s', user_id)
        skin_color_id_key = 'skin_color_id'

        if skin_color_id_key not in request.form:
            LOGGER.warning('Capture Session: skin_color_id_key not found in request form')
            abort(403)

        skin_color_id = request.form[skin_color_id_key]

        try:
            skin_color_id = int(skin_color_id)
        except ValueError:
            LOGGER.warning('Capture Session: Could not convert skin_color_id to int')
            abort(403)

        insertNewSessionQuery = 'INSERT INTO capture_sessions (user_id, skin_color_id, out_of_date) VALUES (%s, %s, %s)'
        data = (user_id, skin_color_id, False)

        with conn.cursor() as cursor:
            cursor.execute(insertNewSessionQuery, data)
            conn.commit()

        # Save updated session info in db

    # GET and POST both return same info

    getCurrentCaptureSession = ('SELECT session_id, skin_color_id, start_date, out_of_date, NOW()::TIMESTAMP FROM capture_sessions',
                                'WHERE user_id=(%s) AND start_date = (SELECT max(start_date)'
                                'FROM capture_sessions WHERE user_id=(%s))')
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

    currentUserSessionObj = {}
    currentUserSessionObj['session_id'] = currentUserSession[0]
    currentUserSessionObj['skin_color_id'] = currentUserSession[1]
    currentUserSessionObj['start_date'] = str(currentUserSession[2]) #Convert dates to strings so jsonify doesnt mess with them
    currentUserSessionObj['out_of_date'] = currentUserSession[3]
    currentUserSessionObj['now'] = str(currentUserSession[4])

    return jsonify(currentUserSessionObj)

@webApp.route('/users/<user_id>/capture', methods=['POST'])
def user_capture(user_id):
    """Adds a new capture for the user"""

    if request.method == 'POST':
        LOGGER.info('Received new user capture')

        if not isUserTokenValid(user_id, request):
            LOGGER.warning('User Not Valid :: user_id: %s', user_id)
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
            LOGGER.warning('Capture: Could not load parameters JSON')
            abort(403)

        if not images:
            LOGGER.warning('Capture: No images in request')
            abort(403)

        # PASSED IN:     user_id | session_id | app_version | device_info
        # FILES:    capture_metadata | capture_data
        # GENERATE: capture_id | capture_date | capture_path

        session_id_key = 'session_id'
        app_version_key = 'app_version'
        device_info_key = 'device_info'
        metadata_key = 'metadata'

        if session_id_key not in parameters:
            LOGGER.warning('Capture: session_id_key not in parameters')
            abort(403)

        session_id = parameters[session_id_key]

        try:
            session_id = int(session_id)
        except ValueError:
            LOGGER.warning('Capture: Could not convert session_id to int')
            abort(403)

        #Check that it is the most recent session... Or at least that session exists?
        captureSessionQuery = 'SELECT skin_color_id, start_date, out_of_date FROM capture_sessions WHERE session_id=(%s) AND user_id=(%s)'
        data = (session_id, user_id)

        with conn.cursor() as cursor:
            cursor.execute(captureSessionQuery, data)
            sessionData = cursor.fetchone()

        if sessionData is None:
            LOGGER.warning('Capture: could not find capture session for user_id %s', user_id)
            abort(403)

        if app_version_key not in parameters:
            LOGGER.warning('Capture: app_version_key not in parameters')
            abort(403)

        app_version = parameters[app_version_key]

        if device_info_key not in parameters:
            LOGGER.warning('Capture: device_info_key not in parameters')
            abort(403)

        device_info = parameters[device_info_key]

        try:
            device_info = json.loads(device_info)
        except ValueError:
            LOGGER.warning('Capture: Could not load device info JSON')
            abort(403)

        if metadata_key not in parameters:
            LOGGER.warning('Capture: metadata_key not in parameters')
            abort(403)

        metadata = parameters[metadata_key]

        try:
            metadata = json.loads(metadata)
        except ValueError:
            LOGGER.warning('Capture: Could not load metadata JSON')
            abort(403)

        insertNewCaptureQuery = ('INSERT INTO captures (session_id, user_id, app_version, device_info, capture_metadata)',
                                 'VALUES (%s, %s, %s, %s, %s)',
                                 'RETURNING capture_id')
        data = (session_id, user_id, app_version, json.dumps(device_info), json.dumps(metadata))

        with conn.cursor() as cursor:
            cursor.execute(insertNewCaptureQuery, data)
            capture_id = cursor.fetchone()[0]
            conn.commit()

        userSessionCapturePath = '{}/{}/{}'.format(str(user_id), str(session_id), str(capture_id))

        LOGGER.info('Capture: Saving data to S3 path tone-user-captures::%s', userSessionCapturePath)
        for imageName, image in images:
            secureImageName = secure_filename(imageName + '.png')
            imagePath = '{}/{}'.format(userSessionCapturePath, secureImageName)
            s3_client.put_object(Bucket=TONE_USER_CAPTURES_BUCKET, Key=imagePath, Body=image)

        metadataPath = '{}/{}'.format(userSessionCapturePath, 'metadata.json')
        s3_client.put_object(Bucket=TONE_USER_CAPTURES_BUCKET, Key=metadataPath, Body=json.dumps(metadata))

        LOGGER.info('Capture: Added Task to SQS :: (user_id, session_id, capture_id) : (%s, %s, %s)', user_id, session_id, capture_id)
        colorMatchMessage = {}
        colorMatchMessage['user_id'] = user_id
        colorMatchMessage['session_id'] = session_id
        colorMatchMessage['capture_id'] = capture_id
        colorMatchMessageJson = json.dumps(colorMatchMessage)

        try:
            queue_response = sqs_queue.send_message(MessageBody=colorMatchMessageJson)
            LOGGER.info('Capture: SQS Response :: %s', queue_response)
        except Exception as e:
            LOGGER.error('Capture: Error adding task to SQS for (user_id, session_id, capture_id) : (%s, %s, %s)\n%s', user_id, session_id, capture_id, e)
            return str(e)
        except:
            LOGGER.error('Capture: Error adding task to SQS for (user_id, session_id, capture_id) : (%s, %s, %s)', user_id, session_id, capture_id)
            return 'And Unknown error occured'
        else:
            LOGGER.info('Capture: Success (user_id, session_id, capture_id) : (%s, %s, %s)', user_id, session_id, capture_id)
            return colorMatchMessageJson

    LOGGER.warning('No matching Request Method in \'/users/%s/capture\' for %s', user_id, request.method)
    abort(404)
    return None
