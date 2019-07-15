from __future__ import print_function
from torchvision.datasets import DatasetFolder
import numpy as np
import pathlib
import imageio
import cv2
import random
import matplotlib.pyplot as plt
import hdr_image_utils
import time

IMG_EXTENSIONS_local = ('.png', '.bmp')
IMAGE_MAX_VALUE = 255
IMAGE_SCALE = 100

def ldr_loader(path, trainMode):
    """
    load npy files that contain the loaded HDR file, and binary image of windows centers.
    :param path: image path
    :return:
    """
    # print("-----ldr")
    # start = time.time()
    path = pathlib.Path(path)
    im_origin = imageio.imread(path)
    # print("load image ",time.time() - start)
    # start = time.time()
    if im_origin.shape[0] < 128:
        print(path)
    if im_origin.shape[1] < 128:
        print(path)
    if trainMode:
        height = im_origin.shape[0] - 128
        width = im_origin.shape[1] - 128
        rand_x = random.randint(0, width)
        rand_y = random.randint(0, height)
        im = im_origin[rand_y: rand_y + 128, rand_x: rand_x + 128]
    else:
        im = cv2.resize(im_origin, (128, 128))
    # print("slice image ",time.time() - start)
    im100 = (im / IMAGE_MAX_VALUE) * IMAGE_SCALE
    im_log = np.log(im100 + 1)
    return im_log

class LdrDatasetFolder(DatasetFolder):
    """
    A customized data loader, to load .npy file that contains a dict
    of numpy arrays that represents hdr_images and window_binary_images.
    """

    def __init__(self, root, trainMode, transform=None, target_transform=None,
                 loader=ldr_loader):
        super(LdrDatasetFolder, self).__init__(root, loader, IMG_EXTENSIONS_local,
                                                     transform=transform,
                                                     target_transform=target_transform)
        self.imgs = self.samples
        self.trainMode = trainMode

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (sample, target) where target is class_index of the target class.
        """
        path, target = self.samples[index]
        sample = self.loader(path, self.trainMode)
        if self.transform is not None:
            sample = self.transform(sample)
        if self.target_transform is not None:
            target = self.target_transform(target)
        return sample, target
