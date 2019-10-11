import numpy as np
import random
import json
from glob import glob
import keras
from keras.models import model_from_json,load_model
from keras.preprocessing.image import ImageDataGenerator
from keras.callbacks import  ModelCheckpoint,Callback,LearningRateScheduler, TensorBoard
import keras.backend as K
from model import Unet_model
from model_simple import Unet_model_simple
import vikas_models as v
from losses import *
#from keras.utils.visualize_util import plot
#from extract_patches import *
#from model_unet_git import unet
from data_generator import DataGenerator
import os
import tensorflow as tf
from keras.backend.tensorflow_backend import set_session
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
# config.gpu_options.per_process_gpu_memory_fraction = 0.45
config.gpu_options.visible_device_list = "0"
set_session(tf.Session(config=config))

# Training Utils function
def schedule_steps(epoch, steps):
    for step in steps:
        if step[1] > epoch:
            print("Setting learning rate to {}".format(step[0]))
            return step[0]
    print("Setting learning rate to {}".format(steps[-1][0]))
    return steps[-1][0]

class SGDLearningRateTracker(Callback):

    def on_epoch_begin(self, epoch, logs={}):
        if epoch%1 == 0 and epoch !=0:
            optimizer = self.model.optimizer
            lr = K.get_value(optimizer.lr)
            decay = K.get_value(optimizer.decay)
            lr = 0.005* (-np.sin((epoch*360./10.)*np.pi/180. )+1)
            # decay=decay*5
            K.set_value(optimizer.lr, lr)
            K.set_value(optimizer.decay, decay)
            print('LR changed to:',lr)
            print('Decay changed to:',decay)


from keras.callbacks import LearningRateScheduler
lrSchedule = LearningRateScheduler(lambda epoch: schedule_steps(epoch, [(5e-3, 2), (3e-3, 5), (1e-3, 5), (1e-4, 5), (5e-4, 2), (1e-4, 5)]))


class Training(object):
    

    def __init__(self, batch_size, nb_epoch, nchannels=1, name=None, load_model_resume_training=None):

        self.batch_size = batch_size
        self.nb_epoch = nb_epoch

        #loading model from path to resume previous training without recompiling the whole model
        if load_model_resume_training is not None:
            self.model =load_model(load_model_resume_training,custom_objects={'gen_dice_loss': gen_dice_loss,'dice_whole_metric':dice_whole_metric,'dice_core_metric':dice_core_metric,'dice_en_metric':dice_en_metric})
            print("pre-trained model loaded!")
        else:
            #self.model = v.unet_densenet121_imagenet(input_shape=(256, 256))
            unet = Unet_model_simple(img_shape=(240, 240, nchannels))
            self.model= unet.model #.compile_unet()
            sgd = keras.optimizers.SGD(lr=0.01, momentum=0.9, decay=5e-6, nesterov=False)
            self.model.compile(loss=gen_dice_loss,
                    optimizer= sgd,
                    metrics=[dice_whole_metric, dice_core_metric, dice_en_metric])
            #self.model.load_weights('/home/brats/parth/checkpoints/unet_mc/UnetRes.90_1.538.hdf5')
            print("U-net CNN compiled!")

        self.name=name


    def fit_unet(self, train_gen, val_gen, save_root=None):

        train_generator = train_gen
        val_generator = val_gen

        if not os.path.exists(save_root):
            os.makedirs(save_root)
            os.mkdir(os.path.join(save_root, 'logs'))

        tb = TensorBoard(log_dir=os.path.join(save_root, 'logs'), histogram_freq=0, batch_size=8, write_graph=True, write_grads=False, write_images=False, embeddings_freq=0, embeddings_layer_names=None, embeddings_metadata=None, embeddings_data=None, update_freq='epoch')
        

        checkpointer = ModelCheckpoint(filepath=os.path.join(save_root, self.name + '.hdf5'), verbose=1, period = 1, save_best_only=True)
        self.model.fit_generator(train_generator,
                                 epochs=self.nb_epoch, steps_per_epoch=len(train_generator), validation_data=val_generator, validation_steps=len(val_generator),  verbose=1,
                                 callbacks=[checkpointer, tb, lrSchedule])

    

    def img_msk_gen(self,X33_train,Y_train,seed):

        '''
        a custom generator that performs data augmentation on both patches and their corresponding targets (masks)
        '''
        datagen = ImageDataGenerator(horizontal_flip=True,data_format="channels_last")
        datagen_msk = ImageDataGenerator(horizontal_flip=True,data_format="channels_last")
        image_generator = datagen.flow(X33_train,batch_size=self.batch_size,seed=seed)
        y_generator = datagen_msk.flow(Y_train,batch_size=self.batch_size,seed=seed)
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
    # model_to_load="Models/ResUnet.04_0.646.hdf5" 
    #save=None

    #compile the model

    for seq in ['flair', 't2']:

        brain_seg = Training(batch_size=4, nb_epoch=10, name='model-wts-'+seq) #, load_model_resume_training = '../checkpoints/densenet_121_sin/dense.hdf5')

        print("number of trainabale parameters:",brain_seg.model.count_params())
        print(brain_seg.model.summary())
        
        train_generator = DataGenerator('/home/brats/parth/slices/train/', batch_size=4, seq=seq)
        val_generator = DataGenerator('/home/brats/parth/slices/val/', batch_size=4, seq=seq)
        
        save_root = '/home/brats/parth/saved_models/model_{}_scaled/'.format(seq)
        os.makedirs(save_root, exist_ok=True)
        brain_seg.model.save(os.path.join(save_root, 'model-archi.h5'))
        brain_seg.fit_unet(train_generator, val_generator, save_root)




