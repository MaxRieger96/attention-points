import numpy as np
import tensorflow as tf
import models.pointnet2_sem_seg as model
from scannet_dataset import precompute_dataset
from scannet import pc_util
from benchmark import util_3d

N_POINTS = 8192
N_VAL_SAMPLES = 20000
BATCH_SIZE = 1

def map_back(values, original_idx, mask, res_shape):
    print("len mask:", len(mask), "len values", len(values), "len original idx", len(original_idx))
    values = np.array(values)
    values = values[mask]
    id_unique = len(np.unique(original_idx))
    print("unique point ids: %s" % id_unique)
    original_idx = original_idx[mask]

    res = np.zeros(res_shape)
    #for id in original_idx:
    #    res[id] = values[id-1] # TODO I think this -1 here is not correct, but it fixes the problem
    res[original_idx] = values
    #print(np.where(res == -2))
    return res

def map_to_nyu40(labels):
    labels = np.array(labels)
    nyu40_labels = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12, 13: 14, 14: 16, 15: 24, 16: 28,
           17: 33, 18: 34, 19: 36, 20: 39}
    #nyu40_labels_map = np.array([nyu40_labels.get(i, 0) for i in range(41)])
    #labels = np.minimum(labels, 40)
    for i in range(len(labels)):
        labels[i] = nyu40_labels.get(labels[i], 1)
    return labels

def train(batch_size=BATCH_SIZE):
    tf.Graph().as_default()
    # tf.device('/gpu:0')
    tf.reset_default_graph()
    gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.9)
    sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))

    # define validation data
    #val_data = precompute_dataset.generate_eval_data(312)
    val_data = precompute_dataset.eval_dataset_from_generator()
    val_data = val_data.batch(batch_size)
    val_iterator = tf.data.Iterator.from_structure(val_data.output_types, val_data.output_shapes)
    val_data_init = val_iterator.make_initializer(val_data)
    sess.run(val_data_init)
    points, labels, colors, normals, scene_name, mask, points_orig_idxs = val_iterator.get_next()
    colors = tf.div(tf.cast(colors, tf.float32), tf.constant(255, dtype=tf.float32))
    val_features = tf.concat([tf.cast(colors, tf.float32), normals], 2)
    #val_features = tf.cast(colors, tf.float32) only for colors
    val_coordinates = points
    val_labels = labels


    # define model and metrics
    is_training_pl = tf.Variable(False)

    # validation metrics
    val_pred, _ = model.get_model(val_coordinates, is_training_pl, 21)

    # Filter out the unassigned labels
    val_labels_flat = tf.reshape(val_labels, [-1])
    val_pred_flat = tf.reshape(val_pred, [-1, val_pred.shape[2]])

    loc = tf.reshape(tf.where(val_labels_flat > 0), [-1])
    val_labels_assigned = tf.gather(val_labels_flat, loc)
    val_pred_assigned = tf.gather(val_pred_flat, loc)
    correct_val_pred = tf.equal(tf.argmax(val_pred_assigned, 1, output_type=tf.int32), val_labels_assigned)

    val_acc = tf.reduce_sum(tf.cast(correct_val_pred, tf.float32)) / \
              tf.cast(tf.shape(val_labels_assigned)[0], tf.float32)
    val_iou, val_iou_update = tf.metrics.mean_iou(val_labels_assigned,
                                                  tf.argmax(val_pred_assigned, 1, output_type=tf.int32),
                                                  num_classes=21, name="val_iou")
    # initialize variables
    variable_init = tf.global_variables_initializer()

    sess.run(variable_init)
    sess.run(tf.local_variables_initializer())
    saver = tf.train.Saver()
    #get_checkpoint = tf.train.latest_checkpoint("/home/tim/training_log/pointnet_and_features/long_run1563786310_continued_train")
    #get_checkpoint = tf.train.latest_checkpoint("/home/tim/training_log/baseline/color_test_run_1563999967_train")
    get_checkpoint = tf.train.latest_checkpoint("/home/tim/training_log/baseline/long_run1563533884_train")
    saver.restore(sess, get_checkpoint)

    val_batches = N_VAL_SAMPLES // BATCH_SIZE
    print(f"starting evaluation all batches")
    all_pred = []
    all_labels = []
    all_points = []
    all_masks = []
    all_points_orig_idxs = []
    current_scene = ""
    while True:
        predictions_res_temp, labels_res, points_res, scene, thefeatures, acc_train, train_iou_val, colorres, pointerres_orig, maskerrades = sess.run([val_pred, val_labels, val_coordinates, scene_name, val_features, val_acc, val_iou, colors, points_orig_idxs, mask])

        # remove unused single batch dimension
        predictions_res = np.squeeze(predictions_res_temp)
        max_pred = np.argmax(predictions_res, axis=1)
        points_res = np.squeeze(points_res)
        labels_res = np.squeeze(labels_res)
        pointerres_orig = np.squeeze(pointerres_orig)
        maskerrades = np.squeeze(maskerrades)



        #print(f"\taccuracy: {acc_train:.4f}\taccumulated iou: {train_iou_val:.4f}")
        if scene != current_scene and current_scene != "":
            print("got all for one scene so please evaluate this scene")
            print(len(np.unique(pointerres_orig)))
            all_points = np.concatenate(all_points)
            all_pred = np.concatenate(all_pred)
            all_labels = np.concatenate(all_labels)
            all_masks = np.concatenate(all_masks)
            all_masks = np.array(all_masks, dtype=bool)
            all_points_orig_idxs = np.concatenate(all_points_orig_idxs)

            restored_labels = map_back(all_labels, all_points_orig_idxs, all_masks, (len(np.unique(all_points_orig_idxs))))
            restored_points = map_back(all_points, all_points_orig_idxs, all_masks, (len(np.unique(all_points_orig_idxs)), 3))
            remapped_pred = map_back(all_pred, all_points_orig_idxs, all_masks, (len(np.unique(all_points_orig_idxs))))
            '''np.save("/home/tim/results/for_visualization/points/%s.npy" % current_scene[0].decode('ascii'),
                    restored_points)
            np.save("/home/tim/results/for_visualization/labels_baseline/%s.npy" % current_scene[0].decode('ascii'),
                    remapped_pred)
            np.save(
                "/home/tim/results/for_visualization/groundtruth_labels/%s.npy" % current_scene[0].decode('ascii'),
                restored_labels)'''

            remapped_pred = map_to_nyu40(remapped_pred)
            #print("original points", pointerres_orig.shape)
            #print("restored points", restored_points.shape, restored_points)
            #print("unchanged values", np.sum(restored_points == -2) / 3, "total values",
            #      np.sum(np.ones_like(restored_points)) / 3)


            output_predictions = "/home/tim/results/predictions_less_smart/%s.txt" % current_scene[0].decode('ascii')
            util_3d.export_ids(output_predictions, remapped_pred)




            #image1 = pc_util.point_cloud_three_views(all_points)
            #img = Image.fromarray(np.uint8(image1 * 255.0))
            #img.save(scene[0].decode('ascii') + "_3views.jpg")
            #image = pc_util.point_cloud_to_image(all_points, 500)
            #img = Image.fromarray(np.uint8(image * 255.0))
            #img.save(scene[0].decode('ascii') + "toImage.jpg")
            # uvidx, uvlabel, nvox = pc_util.point_cloud_label_to_surface_voxel_label(all_points, all_pred)  # res=

            all_pred = []
            all_labels = []
            all_points = []
            all_points_orig_idxs = []
            all_masks = []
        all_pred.append(max_pred)
        all_labels.append(labels_res)
        all_points.append(points_res)
        all_points_orig_idxs.append(pointerres_orig)
        all_masks.append(maskerrades)
        current_scene = scene

if __name__ == '__main__':
    train()
