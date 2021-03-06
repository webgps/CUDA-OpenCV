import numpy as np
import tensorflow as tf

# For tensorflow/stream_executor/cuda/cuda_dnn.cc:329] Could not create cudnn handle: CUDNN_STATUS_INTERNAL_ERROR
# Problem with RTX2070 GPU
from tensorflow.compat.v1 import InteractiveSession
config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth = True
session = InteractiveSession(config=config)
# End RTX2070

import cv2 as cv
from timeit import default_timer as timer

# labelImg test_io.py thanks to https://github.com/tzutalin/labelImg
# Unserstand the xml format https://towardsdatascience.com/coco-data-format-for-object-detection-a4c5eaf518c5
from libs.pascal_voc_io import PascalVocWriter

# File and path modifications
import glob
from pathlib import Path, PurePosixPath, PurePath
import os

# For copying files
import shutil

# TODO: Pass on cli!
modelpath="/home/jarleven/EXPORTED/frozen_inference_graph.pb"
inputpath="/tmp/ramdisk/full/"
rootpath="/tmp/ramdisk/annotated"
rootpathdebug="/tmp/ramdisk/annotateddebug"
xmlpathheader="/home/jarleven/tmp"
scorelimit="0.9"

import sys, getopt

# MAGIC STRINGS AND NUMBERS
objectname="salmon"



def printHelp():
    print("")
    print('python3 test.py -i <inputfolder> -o <xmlfolder> -d <annotatedfolder> -m <modelfile> -l <scorelimit>')
    print("")

def debugParams():
    print(" Test model ")
    print("Input folder is  : ", inputpath)
    print("Output folder is : ", rootpath)
    print("Debug folder is  : ", rootpathdebug)
    print("Model file is    : ", modelpath)
    print("Scorellimit is   : ", scorelimit)

    print("")


try:
    opts, args = getopt.getopt(sys.argv[1:],"hi:o:d:m:l:t",["inputpath=","outputpath=","debugpath=","modelfile=","scorelimit=","test="])
except getopt.GetoptError:
      print("Arguments error")
      debugParams()
      printHelp()
      sys.exit(2)
for opt, arg in opts:
    if opt == '-h':
       printHelp()
       sys.exit()
    elif opt in ("-i", "--inputpath"):
       inputpath = arg
    elif opt in ("-o", "--outputpath"):
       rootpath = arg
    elif opt in ("-d", "--debugpath"):
       rootpathdebug = arg
    elif opt in ("-m", "--modelfile"):
       modelpath = arg
    elif opt in ("-l", "--scorelimit"):
       scorelimit = arg
    elif opt in ("-t", "--test"):
       debugParams()
       sys.exit()



# TODO add params
#   Swrite xml optional
#   verbose
#   Create folders if they don't exist

path = PurePath(modelpath)
modelpathname=path.parent.name

print(modelpathname)

JPGSTR="*.jpg"

# The files to process
# TODO there is a job to do regarding paths
#filenames = glob.glob(inputpath+"*.jpg")
filenames = glob.glob(inputpath+JPGSTR)
filenames.sort()

#
# For tensorflow 2.1. File was upgraded with 
# tf_upgrade_v2 --infile test_model.py --outfile test_model_v21.py
#
#




from datetime import datetime



# Read the graph.
with tf.io.gfile.GFile(modelpath, 'rb') as f:
    graph_def = tf.compat.v1.GraphDef()
    graph_def.ParseFromString(f.read())



with tf.compat.v1.Session() as sess:
    # Restore session
    sess.graph.as_default()
    tf.import_graph_def(graph_def, name='')
    imgnum=0
    totalhits=0
    print("\nStarting object detection\nThere are %d items of type %s\n" % (len(filenames), JPGSTR))


    start = timer()
    #while True:
    for name in filenames:
        
        cap = cv.VideoCapture(name)
        ret, img = cap.read()

        if ret == False:
            break

        imgnum=imgnum+1
           
        rows = img.shape[0]
        cols = img.shape[1]
        inp = cv.resize(img, (800, 800))
        inp = inp[:, :, [2, 1, 0]]  # BGR2RGB

        #TODO get the depth from the image

        filename=PurePosixPath(name).name
        filexml=Path(name).stem + '.xml'
        filepng=Path(name).stem + '.png'

        printname=Path(name).stem


        xmlfilepath=PurePath(rootpath, filexml)
        jpgfilepath=PurePath(rootpath, filename)

        debugfilepath=PurePath(rootpathdebug, Path(name).stem + '.png')


        depth=3  # TODO Depth is 3 for color images, how to read this out
        writer = PascalVocWriter(xmlpathheader, filename, (cols, rows, depth))
        difficult = 1

        # print("File [%s] Object [%s] width [%d]   height [%d]  depth [%d]" % (filename, objectname, cols, rows, depth))

    
        
        # Run the model
        out = sess.run([sess.graph.get_tensor_by_name('num_detections:0'),
                    sess.graph.get_tensor_by_name('detection_scores:0'),
                    sess.graph.get_tensor_by_name('detection_boxes:0'),
                    sess.graph.get_tensor_by_name('detection_classes:0')],
                    feed_dict={'image_tensor:0': inp.reshape(1, inp.shape[0], inp.shape[1], 3)})


        # Visualize detected bounding boxes.
        hit=False

        maxscore_img=0
        num_detections = int(out[0][0])
        for i in range(num_detections):
            classId = int(out[3][0][i])
            score = float(out[1][0][i])
            bbox = [float(v) for v in out[2][0][i]]
            if score > float(scorelimit):
                if score > maxscore_img:
                    maxscore_img = score
                x = bbox[1] * cols
                y = bbox[0] * rows
                right = bbox[3] * cols
                bottom = bbox[2] * rows

                xmin=int(x)
                ymin=int(y)
                xmax=int(right)
                ymax=int(bottom)

                #crop_img = img[ymin:ymin+ymax, xmin:xmin+xmax].copy()
                #cv.imwrite(os.path.join("/home/jarleven/crop/" , filepng),crop_img)


                cv.rectangle(img, (xmin, ymin), (xmax, ymax), (125, 255, 51), thickness=2)
                writer.addBndBox(xmin, ymin, xmax, ymax, objectname, difficult)

                hit=hit+1


        if(hit > 0):
            writer.save(xmlfilepath)
            shutil.copyfile(name, jpgfilepath)

            totalhits=totalhits+1


            A=printname.split(".mp4_")
            camdatetime=A[0].split("__")
            time=camdatetime[2].replace("-", ":")


            cv.putText(img, "%s %s frame %s  -- %02d hits with max score %.3f" % ( camdatetime[1], time, A[1], hit, maxscore_img), (50, 50), cv.FONT_HERSHEY_SIMPLEX, 0.8, (125, 255, 51), 2)
            cv.putText(img, "Model %s" % (modelpathname), (50, 80), cv.FONT_HERSHEY_SIMPLEX, 0.6, (125, 255, 51), 2)

            cv.imwrite(os.path.join(rootpathdebug , filepng),img)

            cv.imshow('object detection', cv.resize(img, (800,600)))
            if cv.waitKey(25) & 0xFF == ord('q'):
                cv.destroyAllWindows()
                break

end = timer()

logfile = open('samplefile.txt', 'a')
print('Images %6d Hits %4d   processtime %7.2f seconds Model used %s' % (imgnum, totalhits, (end-start), modelpathname ), file = logfile)
print('Images %6d Hits %4d   processtime %7.2f seconds Model used %s' % (imgnum, totalhits, (end-start), modelpathname))

logfile.close()

