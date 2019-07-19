import numpy as np
import random
import json
from glob import glob
from keras.models import model_from_json,load_model
from keras.preprocessing.image import ImageDataGenerator
from keras.callbacks import  ModelCheckpoint,Callback,LearningRateScheduler
import keras.backend as K
from model import Unet_model
from model_simple import Unet_model_simple
from losses import *
#from keras.utils.visualize_util import plot
from extract_patches import *
from model_unet_git import unet

import tensorflow as tf
from keras.backend.tensorflow_backend import set_session
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
config.gpu_options.visible_device_list = "0"
set_session(tf.Session(config=config))



class SGDLearningRateTracker(Callback):
    def on_epoch_begin(self, epoch, logs={}):
        optimizer = self.model.optimizer
        lr = K.get_value(optimizer.lr)
        decay = K.get_value(optimizer.decay)
        lr=lr/10
        decay=decay*10
        K.set_value(optimizer.lr, lr)
        K.set_value(optimizer.decay, decay)
        print('LR changed to:',lr)
        print('Decay changed to:',decay)



class Training(object):
    

    def __init__(self, nb_epoch,load_model_resume_training=None):

        #self.batch_size = batch_size
        self.nb_epoch = nb_epoch

        #loading model from path to resume previous training without recompiling the whole model
        if load_model_resume_training is not None:
            self.model =load_model(load_model_resume_training,custom_objects={'gen_dice_loss': gen_dice_loss,'dice_whole_metric':dice_whole_metric,'dice_core_metric':dice_core_metric,'dice_en_metric':dice_en_metric})
            print("pre-trained model loaded!")
        else:
            unet = Unet_model(img_shape=(128, 128, 4))
            self.model= unet.model
            print("U-net CNN compiled!")

    def macro_batch_generator(self, val = False):

        while True:

            batch_x = []
            batch_y = []

            #print('Generator')
            for i in range(4):

                    batch_x.append(single_extractor(val)[0])
                    batch_y.append(single_extractor(val)[1])

            #print(np.array(batch_x).shape)

            yield (np.array(batch_x), np.array(batch_y))

    def fit_unet(self):

        #train_generator=self.img_msk_gen(X33_train,Y_train,9999)
        #checkpointer = ModelCheckpoint(filepath='/home/parth/Interpretable_ML/Brain-tumor-segmentation/checkpoints/20_epochs_resnet/ResUnet.{epoch:02d}_{val_loss:.3f}.hdf5', verbose=1)
        print(self.model.output.shape)
        self.model.fit_generator(self.macro_batch_generator(),
                                 steps_per_epoch=5, validation_data=self.macro_batch_generator(val=True), validation_steps=1,
                                 epochs=self.nb_epoch,verbose=1)
        #self.model.fit(X33_train,Y_train, epochs=self.nb_epoch,batch_size=self.batch_size,validation_data=(X_patches_valid,Y_labels_valid),verbose=1, callbacks = [checkpointer,SGDLearningRateTracker()])

    def img_msk_gen(self,X33_train,Y_train,seed):

        '''
        a custom generator that performs data augmentation on both patches and their corresponding targets (masks)
        '''
        datagen = ImageDataGenerator(horizontal_flip=True,data_format="channels_last")
        datagen_msk = ImageDataGenerator(horizontal_flip=True,data_format="channels_last")
        image_generator = datagen.flow(X33_train,batch_size=4,seed=seed)
        y_generator = datagen_msk.flow(Y_train,batch_size=4,seed=seed)
        while True:
            yield(image_generator.next(), y_generator.next())


    def save_model(self, model_name):
        '''
        INPUT string 'model_name': path where to save model and weights, without extension
        Saves current model as json and weights as h5df file
        '''

        model_tosave = '{}.json'.format(model_name)
        weights = '{}.hdf5'.format(model_name)
        json_string = self.model.to_json()
        self.model.save_weights(weights)
        with open(model_tosave, 'w') as f:
            json.dump(json_string, f)
        print ('Model saved.')

    def load_model(self, model_name):
        '''
        Load a model
        INPUT  (1) string 'model_name': filepath to model and weights, not including extension
        OUTPUT: Model with loaded weights. can fit on model using loaded_model=True in fit_model method
        '''
        print ('Loading model {}'.format(model_name))
        model_toload = '{}.json'.format(model_name)
        weights = '{}.hdf5'.format(model_name)
        with open(model_toload) as f:
            m = next(f)
        model_comp = model_from_json(json.loads(m))
        model_comp.load_weights(weights)
        print ('Model loaded.')
        self.model = model_comp
        return model_comp



if __name__ == "__main__":
    #set arguments

    #reload already trained model to resume training
    model_to_load="Models/ResUnet.04_0.646.hdf5" 
    #save=None

    #compile the model
    brain_seg = Training(nb_epoch=20)

    print("number of trainabale parameters:",brain_seg.model.count_params())
    #print(brain_seg.model.summary())
    #plot(brain_seg.model, to_file='model_architecture.png', show_shapes=True)

    #load data from disk
    #Y=np.load("/media/parth/DATA/brats_as_npy/train/y_dataset_1.npy").astype(np.uint8)
    #X=np.load("/media/parth/DATA/brats_as_npy/train/x_dataset_1.npy").astype(np.float32)
    #Y_labels_valid=np.load("/media/parth/DATA/brats_as_npy/val/y_dataset_11.npy").astype(np.uint8)
    #X_patches_valid=np.load("x/media/parth/DATA/brats_as_npy/val/x_dataset_11.npy").astype(np.float32)
    #print("loading patches done\n")

    # fit model
    brain_seg.fit_unet()#*

    #if save is not None:
    #    brain_seg.save_model('models/' + save)




