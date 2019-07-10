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

#IMAGES_DIR = '/home/dmacewen/Projects/colorMatch/images/'
IMAGES_DIR = '/home/dmacewen/Projects/tone/images/'

#CALIBRATIONS_DIR = '/home/dmacewen/Projects/colorMatch/calibrations/'
#CALIBRATION_CAPTURE_COUNT = 16

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
        

    print('A')
    with open(filePath, 'r+') as f:
        print('B')
        lines = f.readlines() #Should only be one value in file, the number of photos taken
        if len(lines) != 0:
            userImageCount = int(lines[0])

        userImageCount = userImageCount + 1
        f.seek(0)
        f.write(str(userImageCount))
        f.truncate()

    print('C')
    if not imageCountFileExists:
        os.chmod(filePath, 0o777)

    return str(userImageCount)


@webApp.route('/')
@webApp.route('/index')
def index():
    return webApp.send_static_file('index.html')

@webApp.route('/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        return 'Getting All Users!'

    if request.method == 'POST':
        return 'Creating a user!'

    abort(404)

@webApp.route('/users/<user_id>', methods=['GET', 'POST'])
def user(user_id):
    if request.method == 'GET':
        return 'This is a user!'

    if request.method == 'POST':
        filePath = IMAGES_DIR + '/' + user_id

        if os.path.exists(filePath):
            return 'User Already Exists!'
        else:
            return 'Creating New users not allowed'
        #    os.mkdir(filePath)

        #os.chmod(filePath, 0o777)

        #return 'Created user ' + user_id + '!'

    abort(404)

@webApp.route('/users/<user_id>/selfie', methods=['GET', 'POST'])
def user_selfies(user_id):
    user_id = user_id.lower()
    if request.method == 'GET':
        return 'Getting All User Selfies!'

    if request.method == 'POST':
        print("Received Selfies AFTER EDIT")

        if not os.path.exists(IMAGES_DIR + '/' + user_id):
            return "User " + user_id + " does not exist!"

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

@webApp.route('/users/<user_id>/selfie/<selfie_id>', methods=['GET'])
def user_selfie(user_id, selfie_id):
    if request.method == 'GET':
        return 'Getting A Selfie!'

    abort(404)
