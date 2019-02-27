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
            os.mkdir(filePath)

        os.chmod(filePath, 0o777)

        return 'Created user ' + user_id + '!'

    abort(404)

@webApp.route('/users/<user_id>/selfie', methods=['GET', 'POST'])
def user_selfies(user_id):
    if request.method == 'GET':
        return 'Getting All User Selfies!'

    if request.method == 'POST':
        print("Received Selfies AFTER EDIT")

        if not os.path.exists(IMAGES_DIR + '/' + user_id):
            return "User " + user_id + " does not exist!"

        metadata = None
        images = []
        fileNames = [key for key in request.files.keys()]
        for fileName in fileNames:
            if fileName == 'metadata':
                metadata = request.files[fileName]
            else:
                images.append([fileName, request.files[fileName]])
                

        #print(str(fileNames))
        #print(str(request.data))

        #print("Request Files " + str(request.files))

        #first_image = request.files["1"]
        #second_image = request.files["2"]
        #third_image = request.files["3"]
        ##fourth_image = request.files["4"]
        #metadata = request.files["metadata"]


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
        metadata.save(metadataPath)
        os.chmod(metadataPath, 0o777)

        #firstImagePath =  imagePath + userImageSetName + '-1.PNG'
        #secondImagePath = imagePath + userImageSetName + '-2.PNG'
        #thirdImagePath = imagePath + userImageSetName + '-3.PNG'
        #fourthImagePath = imagePath + userImageSetName + '-4.PNG'
        #metadataPath = imagePath + userImageSetName + '-metadata.txt'


        #print("Two")
        #first_image.save(firstImagePath)
        #second_image.save(secondImagePath)
        #third_image.save(thirdImagePath)
        #fourth_image.save(fourthImagePath)
        #metadata.save(metadataPath)

        #print("Three")
        #os.chmod(firstImagePath, 0o777)
        #os.chmod(secondImagePath, 0o777)
        #os.chmod(thirdImagePath, 0o777)
        #os.chmod(fourthImagePath, 0o777)
        #os.chmod(metadataPath, 0o777)

        print("Four")
        #error = runSteps.run(user_id, userImageSetName, False, False);
        try:
            colorAndFluxish = runSteps.run(user_id, userImageSetName, False, False);
        except Exception as e:
            return str(e)
        except:
            return 'And Unknown error occured'
        else:
            return jsonify(colorAndFluxish)

        #print("Four point five")
        #if error is None:
        #    print("Five")
        #    return 'Successfully Processed Selfie #' + userImageCount + ' for ' + user_id
        #else:
        #    print("Five point five")
        #    return error

    abort(404)

@webApp.route('/users/<user_id>/selfie_old', methods=['GET', 'POST'])
def user_selfies_old(user_id):
    if request.method == 'GET':
        return 'Getting All User Selfies!'

    if request.method == 'POST':
        print("Received Selfies")

        #fileNames = [key for key in request.files.keys()]
        #for fileName in fileNames:

        #print(str(fileNames))
        #print(str(request.data))
        if not os.path.exists(IMAGES_DIR + '/' + user_id):
            return "User " + user_id + " does not exist!"

        base_image = request.files["base_image"]
        full_flash_image = request.files["full_flash_image"]
        top_flash_image = request.files["top_flash_image"]
        bottom_flash_image = request.files["bottom_flash_image"]
        white_balance = request.files["white_balance"]

        userImageCount = getAndUpdateUserImageCount(user_id)
        userImageSetName = secure_filename(user_id + userImageCount)

        imagePath = IMAGES_DIR + '/' + user_id + '/' + userImageSetName + '/'

        baseImagePath =  imagePath + userImageSetName + '-base.PNG'
        fullFlashImagePath = imagePath + userImageSetName + '-fullFlash.PNG'
        topFlashImagePath = imagePath + userImageSetName + '-topFlash.PNG'
        bottomFlashImagePath = imagePath + userImageSetName + '-bottomFlash.PNG'
        whiteBalancePath = imagePath + userImageSetName + '-whiteBalance.txt'

        if not os.path.exists(imagePath):
            os.mkdir(imagePath)

        os.chmod(imagePath, 0o777)

        base_image.save(baseImagePath)
        full_flash_image.save(fullFlashImagePath)
        top_flash_image.save(topFlashImagePath)
        bottom_flash_image.save(bottomFlashImagePath)
        white_balance.save(whiteBalancePath)

        os.chmod(baseImagePath, 0o777)
        os.chmod(fullFlashImagePath, 0o777)
        os.chmod(topFlashImagePath, 0o777)
        os.chmod(bottomFlashImagePath, 0o777)
        os.chmod(whiteBalancePath, 0o777)

        error = runSteps.run(user_id, userImageSetName, 1, 'PNG', False);
        if error is None:
            return 'Successfully Processed Selfie #' + userImageCount + ' for ' + user_id
        else:
            return error

    abort(404)

@webApp.route('/users/<user_id>/selfie/<selfie_id>', methods=['GET'])
def user_selfie(user_id, selfie_id):
    if request.method == 'GET':
        return 'Getting A Selfie!'

    abort(404)

#@webApp.route('/users/<user_id>/calibrate', methods=['POST'])
#def user_calibrate(user_id):
#    if request.method == 'POST':
#        calibrationCaptures = []
#        for i in range(0, CALIBRATION_CAPTURE_COUNT):
#            filename = "calibrate_" + str(i)
#            calibrationCapture = request.files[filename]
#            calibrationCaptures.append(calibrationCapture)
#
#        userImageSetName = secure_filename(user_id)
#
#        imagePath = CALIBRATIONS_DIR + userImageSetName + '/'
#
#        if not os.path.exists(imagePath):
#            os.mkdir(imagePath)
#
#        os.chmod(imagePath, 0o777)
#
#        
#        for calibrationCapture in calibrationCaptures:
#            filename = secure_filename(calibrationCapture.filename)
#            path = imagePath + filename
#            calibrationCapture.save(path)
#            os.chmod(path, 0o777)
#
#        return 'Successfully Saved Calibration Captures!'
#
#    abort(404)

@webApp.route('/runner/<user_image>', methods=['GET'])
def runner(user_image):
    if request.method == 'GET':
        runSteps.run(user_image)
        return 'Ran get Face color on user image :: ' + user_image

    abort(404)
