# TF1.2
# g++ -std=c++11 tf_interpolate.cpp -o tf_interpolate_so.so -shared -fPIC -I /usr/local/lib/python2.7/dist-packages/tensorflow/include -I /usr/local/cuda-8.0/include -lcudart -L /usr/local/cuda-8.0/lib64/ -O2 -D_GLIBCXX_USE_CXX11_ABI=0

# TF1.4
g++ -std=c++11 tf_interpolate.cpp -o tf_interpolate_so.so -shared -fPIC \
-I /home/tim/anaconda3/envs/tf/lib/python3.6/site-packages/tensorflow/include \
-I /usr/include \
-I /home/tim/anaconda3/envs/tf/lib/python3.6/site-packages/tensorflow/include/external/nsync/public -lcudart \
-L/home/tim/anaconda3/envs/tf/lib/python3.6/site-packages/tensorflow \
-ltensorflow_framework -O2 -D_GLIBCXX_USE_CXX11_ABI=0
