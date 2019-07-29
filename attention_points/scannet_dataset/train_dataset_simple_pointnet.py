import importlib
import os
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf

from attention_points.scannet_dataset import data_transformation

N_POINTS = 8192
N_TRAIN_SAMPLES = 1201
N_VAL_SAMPLES = 312
MODEL = importlib.import_module("models.pointnet2_sem_seg")
MODEL_WITH_COLOR = importlib.import_module("color_scannet.models.pointnet2_color")
LOG_DIR = os.path.join('/tmp/pycharm_project_250/pointnet2_tensorflow/log/iou/both_%s' % int(time.time()))

TRAIN_COLOR = True


def plot_confusion_matrix(df_confusion, title='Confusion matrix', cmap="Greys"):
    plt.matshow(df_confusion, cmap=cmap)  # imshow
    # plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(df_confusion.columns))
    plt.xticks(tick_marks, df_confusion.columns, rotation=45)
    plt.yticks(tick_marks, df_confusion.index)
    # plt.tight_layout()
    plt.ylabel(df_confusion.index.name)
    plt.xlabel(df_confusion.columns.name)
    plt.show()


def train(epochs=1000, batch_size=20, n_epochs_to_val=4):
    tf.Graph().as_default()
    tf.device('/gpu:0')
    gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.9)
    sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))
    # define train
    train_data = data_transformation.get_transformed_dataset("train")
    train_data = train_data.batch(batch_size).prefetch(2)
    train_iterator = tf.data.Iterator.from_structure(train_data.output_types, train_data.output_shapes)
    train_data_init = train_iterator.make_initializer(train_data)
    sess.run(train_data_init)
    points, labels, colors, train_normals, sample_weight = train_iterator.get_next()
    train_features = tf.concat([tf.cast(colors, tf.float32), train_normals], 2)
    train_coordinates = points
    train_labels = labels
    train_sample_weight = sample_weight
    # define validation data
    val_data = data_transformation.get_transformed_dataset("val")
    val_data = val_data.prefetch(2)
    val_iterator = tf.data.Iterator.from_structure(val_data.output_types, train_data.output_shapes)
    val_data_init = val_iterator.make_initializer(val_data)
    sess.run(val_data_init)
    points, labels, colors, normals, sample_weight = train_iterator.get_next()
    val_features = tf.concat([tf.cast(colors, tf.float32), normals], 0)
    val_coordinates = points
    val_labels = labels
    val_sample_weight = sample_weight

    train_writer = tf.summary.FileWriter(LOG_DIR, sess.graph)

    # define model and metrics
    # is_training_pl = tf.constant(True, tf.bool, shape=(), name="is_training")
    is_training_pl = tf.Variable(True)
    # model = AttentionNetModel(is_training=is_training_pl, bn_decay=None, num_class=21)

    # train_pred = model(train_coordinates)
    if TRAIN_COLOR:
        train_pred, _ = MODEL_WITH_COLOR.get_model(train_coordinates, train_normals, is_training_pl, 21)
    else:
        train_pred, _ = MODEL.get_model(train_coordinates, is_training_pl, 21)
    train_loss = tf.losses.sparse_softmax_cross_entropy(labels=train_labels, logits=train_pred,
                                                        weights=train_sample_weight)

    correct_train_pred = tf.equal(tf.argmax(train_pred, 2, output_type=tf.int32), train_labels)

    train_iou, conf_mat = tf.metrics.mean_iou(train_labels, tf.argmax(train_pred, 2, output_type=tf.int32),
                                              num_classes=21)
    train_acc = tf.reduce_sum(tf.cast(correct_train_pred, tf.float32)) / float(batch_size * N_POINTS)
    optimizer = tf.train.AdamOptimizer(1e-3)
    train_op = optimizer.minimize(train_loss)
    # val_pred = model(val_coordinates)
    '''val_loss = tf.losses.sparse_softmax_cross_entropy(labels=val_labels, logits=val_pred,
                                                      weights=val_sample_weight)
    correct_val_pred = tf.equal(tf.argmax(val_pred, 2, output_type=tf.int32), val_labels)
    val_acc = tf.reduce_sum(tf.cast(correct_val_pred, tf.float32)) / \
              tf.cast(tf.shape(labels)[0] * N_POINTS, dtype=tf.float32)'''

    variable_init = tf.global_variables_initializer()
    sess.run(variable_init)
    sess.run(tf.local_variables_initializer())

    tf.summary.scalar('accuracy', train_acc)
    tf.summary.scalar('loss', train_loss)
    tf.summary.scalar('iou', train_iou)
    batches_per_epoch = N_TRAIN_SAMPLES / batch_size
    # batches_per_epoch = 2
    print(f"batches per epoch: {batches_per_epoch}")
    acc_sum, loss_sum = 0, 0
    assign_op = is_training_pl.assign(True)
    sess.run(assign_op)
    print(tf.trainable_variables())

    # initialize lists for confusion matrices
    pred_list = []
    label_list = []
    for i in range(int(epochs * batches_per_epoch)):
        epoch = int((i + 1) / batches_per_epoch) + 1

        merged = tf.summary.merge_all()

        # _, loss_val, acc_val, pred, batch_data, iou, asdf, merged = sess.run([train_op, train_loss, train_acc, train_pred, points, train_iou, conf_mat, merged])
        # extract labels and predictions
        _, loss_val, acc_val, pred_val, labels_val, iou, _, merged_val = sess.run(
            [train_op, train_loss, train_acc, train_pred, train_labels, train_iou, conf_mat, merged])
        import numpy as np
        pred = np.argmax(pred_val, 2)
        acc_sum += acc_val
        loss_sum += loss_val
        print(f"\tbatch {(i + 1) % int(batches_per_epoch)}\tloss: {loss_val}, \taccuracy: {acc_val}, \t iou: {iou}")
        train_writer.add_summary(merged_val, i)
        # save values for confusion matrix for every batch
        pred_list += list(np.argmax(pred_val, axis=-1).flatten())
        label_list += list(labels_val.flatten())
        if (i + 1) % 1 == 0:  # int(batches_per_epoch) == 0 or True:
            # compute conf matrix after epoch finishes
            y_pred = pd.Series(pred_list, name='Predicted')
            y_actu = pd.Series(label_list, name='Actual')
            df_confusion = pd.crosstab(y_actu, y_pred, margins=True)
            # df_confusion = df_confusion / df_confusion.sum(axis=1)
            print(df_confusion)
            df_confusion = df_confusion / np.sum(df_confusion)
            # plot_confusion_matrix(np.log(df_confusion))
            plot_confusion_matrix(df_confusion)
            pred_list, label_list = [], []

            print(f"epoch {epoch} finished")
            # epoch summary
            print(f"mean acc: {acc_sum / batches_per_epoch} \tmean loss: {loss_sum / batches_per_epoch}")
            '''
            acc_sum, loss_sum = 0, 0
            if epoch % n_epochs_to_val == 0 and False:
                assign_op = is_training_pl.assign(False)
                sess.run(assign_op)
                print("starting evaluation")
                for j in range(N_VAL_SAMPLES):
                    loss_val, acc_val = sess.run([val_loss, val_acc])
                    print(f"\tscene {j} eval: \tloss: {loss_val}, \taccuracy: {acc_val}")
                    acc_sum += acc_val
                    loss_sum += loss_val
                print(f"eval: mean acc: {acc_sum / N_VAL_SAMPLES} \tmean loss: {loss_sum / N_VAL_SAMPLES}")
                acc_sum, loss_sum = 0, 0
                assign_op = is_training_pl.assign(True)
                sess.run(assign_op)'''


if __name__ == '__main__':
    train()