import tensorflow as tf
from tensorflow.contrib import slim
from avb.ops import *

def encoder(x, config, eps=None, is_training=True):
    output_size = config['output_size']
    c_dim = config['c_dim']
    df_dim = config['df_dim']
    z_dist = config['z_dist']
    z_dim = config['z_dim']
    eps_dim = config['eps_dim']

    # Center x at 0
    x = 2*x - 1

    # Noise
    if eps is None:
        batch_size = tf.shape(x)[0]
        eps = tf.random_normal(tf.stack([batch_size, eps_dim]))

    bn_kwargs = {
        'scale': True, 'center':True, 'is_training': is_training, 'updates_collections': None
    }

    conv2d_argscope = slim.arg_scope([slim.conv2d],
            activation_fn=tf.nn.elu, kernel_size=(5, 5), stride=2,
            normalizer_fn=None, normalizer_params=bn_kwargs)

    with conv2d_argscope:
        net = slim.conv2d(x, df_dim, scope="conv_0")
        net = add_linear(eps, net, scope="fc_eps_0")
        net = slim.conv2d(net, 2*df_dim, scope="conv_1")
        net = add_linear(eps, net, scope="fc_eps_1")
        net = slim.conv2d(net, 4*df_dim, scope="conv_2")
        net = add_linear(eps, net, scope="fc_eps_2")

    net = flatten_spatial(net)
    net = slim.fully_connected(net, 800, activation_fn=tf.nn.elu, scope='fc_0')

    z = slim.fully_connected(net, z_dim, activation_fn=None, scope='z',
        weights_initializer=tf.truncated_normal_initializer(stddev=1e-5))

    if z_dist == "uniform":
        z = tf.nn.sigmoid(z)

    return z

def adversary(z, x, config, is_training=True):
    z_dim = config['z_dim']
    z_dist = config['z_dist']
    output_size = config['output_size']
    df_dim = 64

    # Center x at 0
    x = 2*x - 1

    n_down = max(min(int(math.log(output_size, 2)) - 2, 4), 0)
    filter_strides = [(1, 1)] * (4 - n_down) + [(2, 2)] * n_down

    bn_kwargs = {
        'scale': True, 'center':True, 'is_training': is_training, 'updates_collections': None
    }

    conv2d_argscope = slim.arg_scope([slim.conv2d],
        activation_fn=None, kernel_size=(5, 5)
    )
    addlinear_argscope = slim.arg_scope([add_linear],
        activation_fn=tf.nn.elu,
        normalizer_fn=slim.batch_norm, normalizer_params=bn_kwargs
    )
    with conv2d_argscope, addlinear_argscope:
        net = slim.conv2d(x, 1*df_dim, stride=filter_strides[0], scope="conv_0")
        net = add_linear(z, net, scope="fc_z_0")
        net = slim.conv2d(net, 2*df_dim, stride=filter_strides[1], scope="conv_1")
        net = add_linear(z, net, scope="fc_z_1")
        net = slim.conv2d(net, 4*df_dim, stride=filter_strides[2], scope="conv_2")
        net = add_linear(z, net, scope="fc_z_2")
        net = slim.conv2d(net, 8*df_dim, stride=filter_strides[3], normalizer_fn=None, scope="conv_3")
        net = add_linear(z, net, scope="fc_z_3", normalizer_fn=None)

    net = flatten_spatial(net)
    T = slim.fully_connected(net, 1, activation_fn=None)

    if z_dist == "gauss":
        T += 0.5 * tf.reduce_sum(z*z, [1], keep_dims=True)

    T = tf.squeeze(T, 1)

    return T
