from scipy import ndimage
from collections import Counter
from core.vggnet import Vgg19
from core.utils_coco import *

import tensorflow as tf
import numpy as np
import pandas as pd
import hickle
import os
import json
import math
import random
os.environ['CUDA_VISIBLE_DEVICES']='1'

def _process_caption_data(caption_file, image_dir, max_length):
    with open(caption_file) as f:
        caption_data = json.load(f)
    # print (caption_data['annotations'])
    # id_to_filename is a dictionary such as {image_id: filename]} 
    id_to_filename = {image['id']: image['file_name'] for image in caption_data['images']}
    # data is a list of dictionary which contains 'captions', 'file_name' and 'image_id' as key.
    data = []
    for annotation in caption_data['annotations']:
        image_id = annotation['image_id']
        annotation['file_name'] = os.path.join(image_dir, id_to_filename[image_id])
        data += [annotation]
    # convert to pandas dataframe (for later visualization or debugging)
    caption_data = pd.DataFrame.from_dict(data)
    del caption_data['id']
    # caption_data.sort_values(by='image_id', inplace=True)
    # caption_data = caption_data.reset_index(drop=True)   
    
    # delete captions if size is larger than max_length
    print "The number of captions before deletion: %d" %len(caption_data)
    caption_data = caption_data.reset_index(drop=True)
    print "The number of captions after deletion: %d" %len(caption_data)
    return caption_data


def _build_vocab(annotations, threshold=1):
    counter = Counter()
    max_len = 0
    for i, caption in enumerate(annotations['caption']):
        words = caption.split(' ') # caption contrains only lower-case words
        for w in words:
            counter[w] +=1
        
        if len(caption.split(" ")) > max_len:
            max_len = len(caption.split(" "))

    vocab = [word for word in counter if counter[word] >= threshold]
    print ('Filtered %d words to %d words with word count threshold %d.' % (len(counter), len(vocab), threshold))

    word_to_idx = {u'<NULL>': 0, u'<START>': 1, u'<END>': 2}
    idx = 3
    for word in vocab:
        word_to_idx[word] = idx
        idx += 1
    print "Max length of caption: ", max_len
    return word_to_idx


def _build_caption_vector(annotations, word_to_idx, max_length=7):
    n_examples = len(annotations)
    captions = np.ndarray((n_examples,max_length+2)).astype(np.int32)   

    for i, caption in enumerate(annotations['caption']):
        words = caption.split(" ") # caption contrains only lower-case words
        words = words[:-1]
        cap_vec = []
        cap_vec.append(word_to_idx['<START>'])
        for word in words:
            cap_vec.append(int(word))
        cap_vec.append(word_to_idx['<END>'])
        
        # pad short caption with the special null token '<NULL>' to make it fixed-size vector
        if len(cap_vec) < (max_length + 2):
            for j in range(max_length + 2 - len(cap_vec)):
                cap_vec.append(word_to_idx['<NULL>']) 
        
        captions[i, :] = np.asarray(cap_vec)
    #for u in captions:
    #    print [idx_to_word[o] for o in u]
    print "Finished building caption vectors"
    return captions


def _build_file_names(annotations):
    image_file_names = []
    id_to_idx = {}
    idx = 0
    image_ids = annotations['image_id']
    file_names = annotations['file_name']
    for image_id, file_name in zip(image_ids, file_names):
        if not image_id in id_to_idx:
            id_to_idx[image_id] = idx
            image_file_names.append(file_name)
            idx += 1

    file_names = np.asarray(image_file_names)
    return file_names, id_to_idx


def _build_image_idxs(annotations, id_to_idx):
    image_idxs = np.ndarray(len(annotations), dtype=np.int32)
    image_ids = annotations['image_id']
    for i, image_id in enumerate(image_ids):
        image_idxs[i] = id_to_idx[image_id]
    return image_idxs

def main():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    # batch size for extracting feature vectors from vggnet.
    batch_size = 100
    # maximum length of caption(number of word). if caption is longer than max_length, deleted.  
    max_length = 7
    # if word occurs less than word_count_threshold in training dataset, the word index is special unknown token.
    word_count_threshold = 1
    # vgg model path 
    vgg_model_path = '/home/jason6582/sfyc/attention-tensorflow/imagenet-vgg-verydeep-19.mat'

    # about 80000 images and 400000 captions for train dataset
    train_data = _process_caption_data(caption_file='/home/jason6582/sfyc/pascal_json/train_aug.json',
                image_dir='/home/jason6582/sfyc/voc_train/aug_image',
                max_length=max_length)
    val_data = _process_caption_data(caption_file='/home/jason6582/sfyc/pascal_json/val_aug.json',
                image_dir='/home/jason6582/sfyc/voc_test/aug_image',
                max_length=20)
    test_data = _process_caption_data(caption_file='/home/jason6582/sfyc/pascal_json/test_aug.json',
                image_dir='/home/jason6582/sfyc/voc_test/aug_image',
                max_length=20)

    idx_to_word = {0:'<NULL>', 1:'<START>', 2:'<END>', 3:'aeroplane', 4:'bicycle', 5:'bird', 6:'boat', 7:'bottle', 8:'bus', \
            9:'car', 10:'cat', 11:'chair', 12:'cow', 13:'diningtable', 14:'dog', 15:'horse', 16:'motorbike', \
            17:'person', 18:'pottedplant', 19:'sheep', 20:'sofa', 21:'train', 22:'tvmonitor'}
    print 'Finished processing caption data'
    save_pickle(train_data, 'pascaldata_aug/train/train.annotations.pkl')
    save_pickle(val_data, 'pascaldata_aug/val/val.annotations.pkl')
    save_pickle(test_data, 'pascaldata_aug/test/test.annotations.pkl')

    word_to_idx = {u'<NULL>': 0, u'<START>': 1, u'<END>': 2}
    for i in range(20):
        word_to_idx[str(i)] = i + 3
    print "word_to_idx", word_to_idx
    save_pickle(word_to_idx, './pascaldata_aug/train/word_to_idx.pkl')
    for split in ['train', 'val', 'test']:
        if split == 'train':
            max_length = 7
        else:
            max_length = 20
        annotations = load_pickle('./pascaldata_aug/%s/%s.annotations.pkl' % (split, split))
        #for cap in annotations['caption']:
        #    print [idx_to_word[int(c)] for c in cap.split()]
        captions = _build_caption_vector(annotations=annotations, word_to_idx=word_to_idx, max_length=max_length)
        #for cap in captions:
        #    print [idx_to_word[int(c)] for c in cap]
        save_pickle(captions, './pascaldata_aug/%s/%s.captions.pkl' % (split, split))

        file_names, id_to_idx = _build_file_names(annotations)
        save_pickle(file_names, './pascaldata_aug/%s/%s.file.names.pkl' % (split, split))

        image_idxs = _build_image_idxs(annotations, id_to_idx)
        save_pickle(image_idxs, './pascaldata_aug/%s/%s.image.idxs.pkl' % (split, split))

        # prepare reference captions to compute bleu scores later
        image_ids = {}
        feature_to_captions = {}
        i = -1
        for caption, image_id in zip(annotations['caption'], annotations['image_id']):
            if not image_id in image_ids:
                image_ids[image_id] = 0
                i += 1
                feature_to_captions[i] = []
            feature_to_captions[i].append(caption.lower() + ' .')
        save_pickle(feature_to_captions, './pascaldata_aug/%s/%s.references.pkl' % (split, split))
        print "Finished building %s caption dataset" %split

    # extract conv5_3 feature vectors
    vggnet = Vgg19(vgg_model_path)
    vggnet.build()
    with tf.Session() as sess:
        tf.initialize_all_variables().run()
        for split in ['train', 'val', 'test']:
            anno_path = './pascaldata_aug/%s/%s.annotations.pkl' % (split, split)
            save_path = './pascaldata_aug/%s/%s.features.hkl' % (split, split)
            annotations = load_pickle(anno_path)
            image_path = list(annotations['file_name'].unique())
            n_examples = len(image_path)

            all_feats = np.ndarray([n_examples, 196, 512], dtype=np.float32)
            # print all_feats.shape
            for start, end in zip(range(0, n_examples, batch_size),
                                range(batch_size, n_examples + batch_size, batch_size)):
                image_batch_file = image_path[start:end]
                # print image_batch_file
                image_batch = np.array(map(lambda x: ndimage.imread(x, mode='RGB'),\
                        image_batch_file))
                # print image_batch
                image_batch = image_batch.astype(np.float32)
                feats = sess.run(vggnet.features, feed_dict={vggnet.images: image_batch})
                all_feats[start:end, :] = feats
                print ("Processed %d %s features.." % (end, split))
            # use hickle to save huge feature vectors
            hickle.dump(all_feats, save_path)
            print ("Saved %s.." % (save_path))

if __name__ == "__main__":
    main()
