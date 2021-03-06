"""
This module provides methods to precompute, save and load training data.
This allows to speed up training, as the random subscenes do not have to be generated on the fly.
"""
import os.path
import pickle
from typing import Generator

import numpy as np
import tensorflow as tf

from attention_points.scannet_dataset import generator_dataset, data_transformation, complete_scene_loader


def precompute_train_data(epochs: int, elements_per_epoch: int, out_dir: str, dataset: tf.data.Dataset,
                          add_epoch: int = 0):
    """
    precomputes train data
    files saved are a tuple of numpy arrays:
    (points(Nx3), labels(N), colors(N,3), normals(Nx3), sample_weight(N))
    N is the number of points needed by the model (default 8192)
    naming scheme: epoch-scene.pickle

    :param epochs: number of epochs to precompute (random chunks do not cover whole scenes, set >=20)
    :param elements_per_epoch: number of elements loaded from dataset for a single epoch
    :param out_dir: directory to save files to
    :param dataset: tensorflow dataset to load scenes from
    :param add_epoch: offset of epoch name (to continue interrupted precomputation)
    :return:
    """
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    sess = tf.Session()
    data_iterator = tf.data.Iterator.from_structure(dataset.output_types, dataset.output_shapes)
    train_data_init = data_iterator.make_initializer(dataset)
    sess.run(train_data_init)
    points, labels, colors, normals, sample_weight = data_iterator.get_next()
    for i in range(epochs):
        for j in range(elements_per_epoch):
            points_val, labels_val, colors_val, normals_val, sample_weight_val = sess.run(
                [points, labels, colors, normals, sample_weight])
            filename = f"{out_dir}/{i + add_epoch:03d}-{j:04d}.pickle"
            if not os.path.isfile(filename):
                with open(filename, "wb")as file:
                    pickle.dump((points_val, labels_val, colors_val, normals_val, sample_weight_val), file)
            else:
                raise ValueError("the file already exists")


def precompute_val_data(elements: int, out_dir: str, dataset: tf.data.Dataset = generator_dataset
                        .get_dataset("val").prefetch(4).map(data_transformation.label_map)):
    """
    precomputes validation data
    files saved are a tuple of numpy arrays:
    (points(Nx3), labels(N), colors(N,3), normals(Nx3), sample_weight(N))
    N is the number of points needed by the model (default 8192)
    naming scheme: scene-subscene.pickle

    :param elements: number of elements to load from dataset
    :param out_dir: directory to save files to
    :param dataset: tensorflow dataset to load scenes from
    """
    sess = tf.Session()
    data_iterator = tf.data.Iterator.from_structure(dataset.output_types, dataset.output_shapes)
    val_data_init = data_iterator.make_initializer(dataset)
    sess.run(val_data_init)
    scene = data_iterator.get_next()
    for i in range(elements):
        scene_val = sess.run([scene])[0]
        points_val, labels_val, colors_val, normals_val = scene_val
        subscenes = data_transformation.get_all_subsets_for_scene_numpy(points_val, labels_val, colors_val, normals_val)
        for j in range(len(subscenes[0])):
            points_val, labels_val, colors_val, normals_val, sample_weight_val = (x[j] for x in subscenes)
            filename = f"{out_dir}/{i:03d}-{j:04d}.pickle"
            if not os.path.isfile(filename):
                with open(filename, "wb")as file:
                    pickle.dump((points_val, labels_val, colors_val, normals_val, sample_weight_val), file)
            else:
                raise ValueError("the file already exists")


def generate_eval_data() -> Generator:
    """
    generator which iterates over precomputed validation set and yields single subsets
    also yields the scene name, a boolean mask for points with meaningful predictions and original point indices

    :return: (points(Nx3), labels(N), colors(Nx3), normals(Nx3), scene_name, mask(N), indices(N))
    """
    for scene_name in generator_dataset.scene_name_generator("val"):
        points_val, labels_val, colors_val, normals_val = generator_dataset.load_from_scene_name(scene_name)
        labels_val = data_transformation.label_map_more_parameters(labels_val.astype(np.int32))
        subscenes = complete_scene_loader.get_all_subsets_with_all_points_for_scene_numpy(points_val, labels_val,
                                                                                          colors_val, normals_val)

        for j in range(len(subscenes[0])):
            points_val, labels_val, colors_val, normals_val, sample_weight_val, mask, points_orig_idxs = (x[j] for x in
                                                                                                          subscenes)
            yield (points_val, labels_val, colors_val, normals_val, scene_name.encode('utf-8'), mask, points_orig_idxs)


def generate_test_data() -> Generator:
    """
    generator which iterates over precomputed test set and yields single subsets
    also yields the scene name, a boolean mask for points with meaningful predictions and original point indices

    :return: (points(Nx3), colors(Nx3), normals(Nx3), scene_name, mask(N), indices(N))
    """
    for scene_name in generator_dataset.scene_name_generator("test"):
        points_val, colors_val, normals_val = generator_dataset.load_from_scene_name_test(scene_name)
        subscenes = complete_scene_loader.get_all_subsets_with_all_points_for_scene_numpy_test(points_val, colors_val,
                                                                                               normals_val)

        for j in range(len(subscenes[0])):
            points_val, colors_val, normals_val, mask, points_orig_idxs = (x[j] for x in subscenes)
            yield (points_val, colors_val, normals_val, scene_name.encode('utf-8'), mask, points_orig_idxs)


def eval_dataset_from_generator() -> tf.data.Dataset:
    """
    tensorflow dataset from eval data generator

    :return: tf dataset
    """
    gen = generate_eval_data
    return tf.data.Dataset.from_generator(gen,
                                          output_types=(tf.float32, tf.int32, tf.int32, tf.float32, tf.string, tf.int32,
                                                        tf.int32),
                                          output_shapes=(tf.TensorShape([None, 3]), tf.TensorShape([None]),
                                                         tf.TensorShape([None, 3]), tf.TensorShape([None, 3]),
                                                         tf.TensorShape([]), tf.TensorShape([None]),
                                                         tf.TensorShape([None])))


def test_dataset_from_generator() -> tf.data.Dataset:
    """
    tensorflow dataset from test data generator

    :return: tf dataset
    """
    gen = generate_test_data
    return tf.data.Dataset.from_generator(gen,
                                          output_types=(tf.float32, tf.int32, tf.float32, tf.string, tf.int32,
                                                        tf.int32),
                                          output_shapes=(tf.TensorShape([None, 3]),
                                                         tf.TensorShape([None, 3]), tf.TensorShape([None, 3]),
                                                         tf.TensorShape([]), tf.TensorShape([None]),
                                                         tf.TensorShape([None])))


def precomputed_train_data_generator(dir: str = "/home/tim/data/train_precomputed") -> Generator:
    """
    iterates over precomputed train data and yields single chunks

    :param dir: directory of precomputed train data
    :return: (points(NX3), labels(N), colors(Nx3), normals(Nx3), sample_weight(N))
    """
    file_list = sorted(os.listdir(dir))
    while True:
        for filename in file_list:
            if filename.endswith(".pickle"):
                file = (os.path.join(dir, filename))
                with open(file, "rb") as file:
                    points_val, labels_val, colors_val, normals_val, sample_weight_val = pickle.load(file)
                    yield points_val, labels_val, colors_val, normals_val, sample_weight_val


def get_precomputed_train_data_set() -> tf.data.Dataset:
    """
    tensorflow dataset from precomputed train data generator

    :return: tf dataset
    """
    gen = precomputed_train_data_generator
    return tf.data.Dataset.from_generator(gen,
                                          output_types=(tf.float32, tf.int32, tf.int32, tf.float32, tf.float32),
                                          output_shapes=(tf.TensorShape([None, 3]), tf.TensorShape([None]),
                                                         tf.TensorShape([None, 3]), tf.TensorShape([None, 3]),
                                                         tf.TensorShape([None])))


def precomputed_val_data_generator(dir: str = "/home/tim/data/val_precomputed") -> Generator:
    """
    iterates over precomputed val data and yields single chunks

    :param dir: directory of precomputed val data
    :return: (points(NX3), labels(N), colors(Nx3), normals(Nx3), sample_weight(N))
    """
    file_list = sorted(os.listdir(dir))
    while True:
        for filename in file_list:
            if filename.endswith(".pickle"):
                file = (os.path.join(dir, filename))
                with open(file, "rb") as file:
                    points_val, labels_val, colors_val, normals_val, sample_weight_val = pickle.load(file)
                    yield points_val, labels_val, colors_val, normals_val, sample_weight_val


def get_precomputed_val_data_set() -> tf.data.Dataset:
    """
    tensorflow dataset from precomputed val data generator

    :return: tf dataset
    """
    gen = precomputed_val_data_generator
    return tf.data.Dataset.from_generator(gen,
                                          output_types=(tf.float32, tf.int32, tf.int32, tf.float32, tf.float32),
                                          output_shapes=(tf.TensorShape([None, 3]), tf.TensorShape([None]),
                                                         tf.TensorShape([None, 3]), tf.TensorShape([None, 3]),
                                                         tf.TensorShape([None])))


def precomputed_train_subset_data_generator(dir: str = "/home/tim/data/train_subset_precomputed") -> Generator:
    """
    iterates over precomputed subset of train data and yields single chunks

    :param dir: directory of precomputed subset of train data
    :return: (points(NX3), labels(N), colors(Nx3), normals(Nx3), sample_weight(N))
    """
    file_list = sorted(os.listdir(dir))
    while True:
        for filename in file_list:
            if filename.endswith(".pickle"):
                file = (os.path.join(dir, filename))
                with open(file, "rb") as file:
                    points_val, labels_val, colors_val, normals_val, sample_weight_val = pickle.load(file)
                    yield points_val, labels_val, colors_val, normals_val, sample_weight_val


def get_precomputed_train_subset_data_set() -> tf.data.Dataset:
    """
    tensorflow dataset from precomputed subset of train data generator

    :return: tf dataset
    """
    gen = precomputed_train_data_generator
    return tf.data.Dataset.from_generator(gen,
                                          output_types=(tf.float32, tf.int32, tf.int32, tf.float32, tf.float32),
                                          output_shapes=(tf.TensorShape([None, 3]), tf.TensorShape([None]),
                                                         tf.TensorShape([None, 3]), tf.TensorShape([None, 3]),
                                                         tf.TensorShape([None])))


def precomputed_val_subset_data_generator(dir: str = "/home/tim/data/val_precomputed") -> Generator:
    """
    iterates over precomputed subset of val data and yields single chunks

    :param dir: directory of precomputed subset of val data
    :return: (points(NX3), labels(N), colors(Nx3), normals(Nx3), sample_weight(N))
    """
    file_list = sorted(os.listdir(dir))
    file_list = file_list[:len(file_list) // 3]
    while True:
        for filename in file_list:
            if filename.endswith(".pickle"):
                file = (os.path.join(dir, filename))
                with open(file, "rb") as file:
                    points_val, labels_val, colors_val, normals_val, sample_weight_val = pickle.load(file)
                    yield points_val, labels_val, colors_val, normals_val, sample_weight_val


def get_precomputed_val_subset_data_set() -> tf.data.Dataset:
    """
    tensorflow dataset from precomputed subset of val data generator

    :return: tf dataset
    """
    gen = precomputed_val_subset_data_generator
    return tf.data.Dataset.from_generator(gen,
                                          output_types=(tf.float32, tf.int32, tf.int32, tf.float32, tf.float32),
                                          output_shapes=(tf.TensorShape([None, 3]), tf.TensorShape([None]),
                                                         tf.TensorShape([None, 3]), tf.TensorShape([None, 3]),
                                                         tf.TensorShape([None])))


def precompute_subset_train_data():
    """
    precomputes data from a subset of the scenes in the training set

    :return:
    """
    ds = data_transformation.get_transformed_dataset("train_subset").prefetch(4)
    precompute_train_data(100, 1201 // 3, "/home/tim/data/train_subset_precomputed", ds, 0)
