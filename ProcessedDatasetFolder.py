import torch
# from __future__ import print_function
from torchvision.datasets import DatasetFolder
import params
import numpy as np

IMG_EXTENSIONS_local = ('.npy')


def npy_loader(path):
    """
    load npy files that contain the loaded HDR file, and binary image of windows centers.
    :param path: image path
    :return:
    """
    image = np.load(path)
    if image.ndim == 2:
        image = image[:, :, None]
    image_tensor = torch.from_numpy(image).float()
    return image_tensor
    # return data
    # return data[()][params.image_key], data[()][params.window_image_key]


class ProcessedDatasetFolder(DatasetFolder):
    """
    A customized data loader, to load .npy file that contains a dict
    of numpy arrays that represents hdr_images and window_binary_images.
    """

    def __init__(self, root, transform=None, target_transform=None,
                 loader=npy_loader):
        super(ProcessedDatasetFolder, self).__init__(root, loader, IMG_EXTENSIONS_local,
                                                     transform=transform,
                                                     target_transform=target_transform)
        self.imgs = self.samples

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            sample: {'hdr_image': im, 'binary_wind_image': binary_im}
        """
        path, target = self.samples[index]
        image = self.loader(path)
        # image, binary_window = self.loader(path)
        # sample = {params.image_key: image, params.window_image_key: binary_window}
        if self.transform:
            image = self.transform(image)
        return image, target
