# Copyright 2021 SVision Technologies LLC.
# Copyright 2021-2022 Leica Microsystems, Inc.
# Creative Commons Attribution-NonCommercial 4.0 International Public License
# (CC BY-NC 4.0) https://creativecommons.org/licenses/by-nc/4.0/

import tensorflow as tf


def _get_spatial_ndim(x):
    return tf.keras.backend.ndim(x) - 2


def _get_num_channels(x):
    return x.shape[-1]


def _conv(x, num_filters, kernel_size, padding='same', **kwargs):
    n = _get_spatial_ndim(x)

    if n == 1:
        conv_func = tf.keras.layers.Conv1D
    elif n == 2:
        conv_func = tf.keras.layers.Conv2D
    elif n == 3:
        conv_func = tf.keras.layers.Conv3D
    else:
        raise NotImplementedError(f'{n}D convolution is not supported')

    return conv_func(num_filters, kernel_size, padding=padding, **kwargs)(x)


def _global_average_pooling(x):
    n = _get_spatial_ndim(x)
    if n == 2:
        return tf.keras.layers.GlobalAveragePooling2D()(x)
    elif n == 3:
        return tf.keras.layers.GlobalAveragePooling3D()(x)
    else:
        raise NotImplementedError(
            f'{n}D global average pooling is not supported'
        )


def _channel_attention_block(x, reduction):
    '''
    Channel attention block.

    References
    ----------
    - Squeeze-and-Excitation Networks
      https://arxiv.org/abs/1709.01507
    - Image Super-Resolution Using Very Deep Residual Channel Attention
      Networks
      https://arxiv.org/abs/1807.02758
    '''

    num_channels = _get_num_channels(x)

    y = _global_average_pooling(x)
    y = tf.keras.layers.Reshape((*(1,) * _get_spatial_ndim(x), num_channels))(
        y
    )
    y = _conv(y, num_channels // reduction, 1, activation='relu')
    y = _conv(y, num_channels, 1, activation='sigmoid')

    return tf.keras.layers.Multiply()([x, y])


def _residual_channel_attention_blocks(
    x, repeat=1, channel_reduction=8, residual_scaling=1.0
):
    num_channels = _get_num_channels(x)

    for _ in range(repeat):
        skip = x

        x = _conv(x, num_channels, 3, activation='relu')
        x = _conv(x, num_channels, 3)

        x = _channel_attention_block(x, channel_reduction)

        if residual_scaling != 1.0:
            x = tf.keras.layers.Lambda(lambda x: residual_scaling * x)(x)

        x = tf.keras.layers.Add()([x, skip])

    return x


@tf.keras.saving.register_keras_serializable(
    package='custom', name='Standardise'
)
class StandardiseLayer(tf.keras.layers.Layer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def call(self, inputs):
        return tf.math.add(tf.math.scalar_mul(2.0, inputs), -1.0)

    def get_config(self):
        return {}


@tf.keras.saving.register_keras_serializable(
    package='custom', name='Destandardise'
)
class DestandardiseLayer(tf.keras.layers.Layer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def call(self, inputs):
        return tf.math.add(tf.math.scalar_mul(0.5, inputs), 0.5)

    def get_config(self):
        return {}


def build_rcan(
    input_shape=(16, 256, 256, 1),
    *,
    num_channels=32,
    num_residual_blocks=3,
    num_residual_groups=5,
    channel_reduction=8,
    residual_scaling=1.0,
    num_output_channels=-1,
):
    '''
    Builds a residual channel attention network. Note that the upscale module
    at the end of the network is omitted so that the input and output of the
    model have the same size.

    Parameters
    ----------
    input_shape: tuple of int
        Input shape of the model.
    num_channels: int
        Number of feature channels.
    num_residual_blocks: int
        Number of residual channel attention blocks in each residual group.
    num_residual_groups: int
        Number of residual groups.
    channel_reduction: int
        Channel reduction ratio for channel attention.
    residual_scaling: float
        Scaling factor applied to the residual component in the residual
        channel attention block.
    num_output_channels: int
        Number of channels in the output image. if negative, it is set to the
        same number as the input.

    Returns
    -------
    keras.Model
        Keras model instance.

    References
    ----------
    Image Super-Resolution Using Very Deep Residual Channel Attention Networks
    https://arxiv.org/abs/1807.02758
    '''

    if num_output_channels < 0:
        num_output_channels = input_shape[-1]

    inputs = tf.keras.layers.Input(input_shape)

    x = StandardiseLayer()(inputs)
    x = _conv(x, num_channels, 3)

    long_skip = x

    for _ in range(num_residual_groups):
        short_skip = x

        x = _residual_channel_attention_blocks(
            x, num_residual_blocks, channel_reduction, residual_scaling
        )

        if num_residual_groups == 1:
            break

        x = _conv(x, num_channels, 3)
        x = tf.keras.layers.Add()([x, short_skip])

    x = _conv(x, num_channels, 3)
    x = tf.keras.layers.Add()([x, long_skip])

    x = _conv(x, num_output_channels, 3)
    outputs = DestandardiseLayer()(x)

    return tf.keras.Model(inputs, outputs)
