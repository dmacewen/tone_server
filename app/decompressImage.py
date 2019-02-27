import base64
import cv2
import numpy as np

SUB_PIXEL_SIZE = 3

def encoded_to_image(image_png_encoded_ascii):
    image_png = base64.urlsafe_b64decode(image_png_encoded_ascii.encode('ascii'))
    image_png_array = np.frombuffer(image_png, 'uint8')
    image = cv2.imdecode(image_png_array, 1)
    return image

def encoded_to_image_two(image_png):
    image_png_array = np.frombuffer(image_png, 'uint8')
    image = cv2.imdecode(image_png_array, 1)
    return image

    #image_buffer_compressed = base64.urlsafe_b64decode(image_buffer_compressed_encoded_ascii.encode('ascii'))
    #image_buffer = lzma.decompress(image_buffer_compressed)

    #image_flat_array = np.frombuffer(image_buffer, np.uint8)
    #image = np.empty([height, width, 3], dtype=np.uint8)

    #for (index, subPixel) in enumerate(image_flat_array):
    #    yIndex = int(index / (SUB_PIXEL_SIZE * width)) % height
    #    xIndex = int(index / SUB_PIXEL_SIZE) % width
    #    subpixelIndex = index % SUB_PIXEL_SIZE
    #    image[yIndex, xIndex, subpixelIndex] = subPixel

    #return image

