# import the necessary packages
from picamera.array import PiRGBArray
from picamera import PiCamera
import warnings
import datetime
import json
import time
import cv2
import requests
import socket

# Class to control start/stop/display state of 
# current looping process

class Looper():

    def __init__(self, confPath='conf.json'):
        self.conf = json.load(open(confPath))
        
    def curState(self):
        """Get current looping state"""
        return 1 if self._isRunning else 0

    def stop(self):
        """Stop loop"""
        print('[INFO] Stop from looper')
        self._isRunning = False

    def start(self):
        """Start loop (if not running yet)"""
        print('[INFO] Start from looper')
        self._isRunning = True
        
        # initialize the camera and grab a reference to the raw camera capture
        camera = PiCamera()
        camera.resolution = tuple(self.conf["resolution"])
        camera.framerate = self.conf["fps"]
        rawCapture = PiRGBArray(camera, size=tuple(self.conf["resolution"]))
        
        # allow the camera to warmup, then initialize the average frame, last
        # uploaded timestamp, and frame motion counter
        print("[INFO] warming up...")
        time.sleep(self.conf["camera_warmup_time"])
        avg = None
        lastUploaded = datetime.datetime.now()
        motionCounter = 0
        print('[INFO] Talking to raspi started')
        
        # capture frames from the camera
        for f in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            if self._isRunning == False:
                print('[INFO] Bye from looper')    
                break
            
            # grab the raw NumPy array representing the image and initialize
            # the timestamp and occupied/unoccupied text
            frame = f.array
            timestamp = datetime.datetime.now()
            text = "No motion"

            ######################################################################
            # COMPUTER VISION
            ######################################################################
            # resize the frame, convert it to grayscale, and blur it
            # TODO: resize image here into smaller sizes 
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, tuple(self.conf['blur_size']), 0)

            # if the average frame is None, initialize it
            if avg is None:
                print("[INFO] starting background model...")
                avg = gray.copy().astype("float")
                rawCapture.truncate(0)
                continue

            # accumulate the weighted average between the current frame and
            # previous frames, then compute the difference between the current
            # frame and running average
            frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
            cv2.accumulateWeighted(gray, avg, 0.5)

            # threshold the delta image, dilate the thresholded image to fill
            # in holes, then find contours on thresholded image
            thresh = cv2.threshold(frameDelta, self.conf["delta_thresh"], 255,
                cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            im2 ,cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE)

            # loop over the contours
            for c in cnts:
                # if the contour is too small, ignore it
                if cv2.contourArea(c) < self.conf["min_area"]:
                    continue

                # compute the bounding box for the contour,
                # draw it on the frame and update the text
                # in required
                #(x, y, w, h) = cv2.boundingRect(c)
                #cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                text = "Minor Motion detected"

            ###################################################################################
            # LOGIC
            ###################################################################################

            # check to see if the room is occupied
            if text == "Minor Motion detected":

                # check to see if enough time has passed between uploads
                if (timestamp - lastUploaded).seconds >= self.conf["min_upload_seconds"]:
                    
                    # increment the motion counter
                    motionCounter += 1

                    # check to see if the number of frames with consistent motion is
                    # high enough
                    if motionCounter >= int(self.conf["min_motion_frames"]):
                        
                        print('[INFO] Real motion detected!')
                        
                        # check to see if we need post frame to the API
                        if self.conf["motion_detected_api"] != "":
                            cv2.imwrite("./motion-detected-img.jpg", frame)
                            files = {'upload_file': open("./motion-detected-img.jpg",'rb')}
                            data = {"node": socket.gethostname()}
                        
                            try:
                                print('[INFO] Trying PUT request with a file')
                                #requests.put(self.conf["motion_detected_api"], files=files, data=data)
                            except requests.exceptions.RequestException as e:
                                print('[ERROR] Request failed', e)
                            else:
                                print('[INFO] Request succeeded')

                        # update the last uploaded timestamp and reset the motion
                        # counter
                        lastUploaded = timestamp
                        motionCounter = 0

            # otherwise, the room is not occupied
            else:
                motionCounter = 0

            # clear the stream in preparation for the next frame
            rawCapture.truncate(0)
