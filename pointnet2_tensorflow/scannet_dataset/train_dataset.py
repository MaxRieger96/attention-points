import tensorflow as tf

from attention_scannet.attention_models import AttentionNetModel
from scannet_dataset import data_transformation


def train(epochs=2, batchsize=16):
    tf.Graph().as_default()
    tf.device('/gpu:0')
    sess = tf.Session()
    # define dataset
    dataset = data_transformation.get_transformed_dataset("train")
    dataset = dataset.batch(batchsize).prefetch(2)
    iterator = tf.data.Iterator.from_structure(dataset.output_types, dataset.output_shapes)
    dataset_init = iterator.make_initializer(dataset)
    sess.run(dataset_init)
    next_element = iterator.get_next()
    points, labels, colors, normals, sample_weight = next_element
    # define model and metrics
    is_training_pl = tf.constant(True, tf.bool, shape=(), name="is_training")
    model = AttentionNetModel(is_training=is_training_pl, bn_decay=None, num_class=21)
    prediction = model(points)
    loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=prediction, weights=sample_weight)

    correct = tf.equal(tf.argmax(prediction, 2), tf.to_int64(labels))
    accuracy = tf.reduce_sum(tf.cast(correct, tf.float32)) / float(batchsize * 8192)
    optimizer = tf.train.AdamOptimizer(1e-3)
    train_op = optimizer.minimize(loss)

    variable_init = tf.global_variables_initializer()
    sess.run(variable_init)

    batches_per_epoch = 1201 / batchsize
    print(f"batches per epoch: {batches_per_epoch}")
    for i in range(int(epochs * batches_per_epoch)):
        epoch = int((i + 1) / batches_per_epoch) + 1
        _, loss_val, pred_val, acc_val = sess.run([train_op, loss, prediction, accuracy])
        print(f"\tbatch {(i + 1) % int(batches_per_epoch)}\tloss: {loss_val}, \taccuracy: {acc_val}")
        if (i + 1) % int(batches_per_epoch) == 0:
            print(f"epoch {epoch} finished")


if __name__ == '__main__':
    train()