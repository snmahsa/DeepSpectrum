import io
import warnings
from os import environ

import matplotlib.pyplot as plt
import numpy as np
from imread import imread_from_blob
from scipy.io import wavfile

environ['GLOG_minloglevel'] = '2'

import caffe


def get_wav_info(wav_file):
    frame_rate, sound_info = wavfile.read(wav_file)
    sound_info = np.trim_zeros(sound_info)
    return sound_info, frame_rate


def graph_spectrogram(wav_file, nfft=256, cmap='viridis', size=227):
    sound_info, frame_rate = get_wav_info(wav_file)
    fig = plt.figure(frameon=False)
    fig.set_size_inches(1, 1)
    ax = plt.Axes(fig, [0., 0., 1., 1.], )
    ax.set_axis_off()
    fig.add_axes(ax)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Pxx, freqs, bins, im = plt.specgram(sound_info, NFFT=nfft, Fs=frame_rate, cmap=cmap, noverlap=int(nfft / 2))
    # extent = im.get_extent()
    plt.xlim([0, len(sound_info) / frame_rate])
    plt.ylim([0, frame_rate / 2])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=size)
    buf.seek(0)
    plt.close('all')
    return buf.read()


def graph_spectrogram_chunks(wav_file, chunksize, step, nfft=256, cmap='viridis', size=227):
    sound_info, frame_rate = get_wav_info(wav_file)
    chunksize = int(chunksize / 1000 * frame_rate)
    step = chunksize if step is None else int(step / 1000 * frame_rate)
    chunks = [sound_info[n * step:min(n * step + chunksize, len(sound_info))] for n in
              range(int((len(sound_info) - chunksize) / step))]
    for chunk in chunks:
        fig = plt.figure(frameon=False)
        fig.set_size_inches(1, 1)
        ax = plt.Axes(fig, [0., 0., 1., 1.], )
        ax.set_axis_off()
        fig.add_axes(ax)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            Pxx, freqs, bins, im = plt.specgram(chunk, NFFT=nfft, noverlap=int(nfft / 2), Fs=frame_rate,
                                                cmap=cmap)
        extent = im.get_extent()
        plt.xlim([extent[0], extent[1]])
        plt.ylim([extent[2], extent[3]])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=size)
        buf.seek(0)
        plt.close('all')
        yield buf.read()


def extract_features(img_blob, input_transformer, caffe_net, layer='fc7'):
    try:
        img = imread_from_blob(img_blob, 'png')
        img = caffe.io.skimage.img_as_float(img).astype(np.float32)
        img = img[:, :, :-1]
    except IOError:
        print('Error while reading the spectrogram blob.')
        return False, None
    img = input_transformer.preprocess('data', img)
    caffe_net.blobs["data"].data[...] = img
    caffe_net.forward()
    return True, caffe_net.blobs[layer].data[0]