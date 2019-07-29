import os
import pickle

import numpy as np
import pptk

g_label_names = ['unannotated', 'wall', 'floor', 'chair', 'table', 'desk', 'bed', 'bookshelf', 'sofa', 'sink',
                 'bathtub', 'toilet', 'curtain', 'counter', 'door', 'window', 'shower curtain', 'refridgerator',
                 'picture', 'cabinet', 'otherfurniture']
g_label_colors = [[1, 1, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0],
                  [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0],
                  [0, 0, 0], [0, 0, 0], [0.2, 0.5, 0]]

# Visualize ground truth
'''output = os.path.join('/tmp/batch.pickle')
with open(output, 'rb') as wfp:
    points = pickle.load(wfp, encoding='latin1')
    segments = pickle.load(wfp, encoding='latin1')
x = points[0]
colors = list(map(lambda label: g_label_colors[int(label)], segments[0]))
v = pptk.viewer(points[0], colors)
v.set(point_size=0.005)'''

# Visualize prediction
output2 = os.path.join('/tmp/batch_prediction.pickle')
with open(output2, 'rb') as wfp2:
    points2 = pickle.load(wfp2, encoding='latin1')
    segments2 = pickle.load(wfp2, encoding='latin1')

colors2 = list(map(lambda label: g_label_colors[int(label)], segments2[0]))
v2 = pptk.viewer(points2[0], colors2)
v2.set(point_size=0.005)
# add animation
poses = []
poses.append([2, 0, 0, 0 * np.pi / 2, np.pi / 4, 10])
poses.append([2, 0, 0, 1 * np.pi / 2, np.pi / 4, 10])
poses.append([2, 0, 0, 2 * np.pi / 2, np.pi / 4, 10])
poses.append([2, 0, 0, 3 * np.pi / 2, np.pi / 4, 10])
poses.append([2, 0, 0, 4 * np.pi / 2, np.pi / 4, 10])
v2.play(poses, 2 * np.arange(5), repeat=True, interp='linear')
print(1)