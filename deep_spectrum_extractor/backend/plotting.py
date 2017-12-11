import io
import warnings

import matplotlib

# force matplotlib to not use X-Windows backend. Needed for running the tool through an ssh connection.
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import librosa.display
import numpy as np
import soundfile as sf
import pathlib
from imread import imread_from_blob
from os import environ, makedirs
from os.path import basename, join, dirname
from multiprocessing import cpu_count, Pool
from functools import partial

environ['GLOG_minloglevel'] = '2'


def _read_wav_data(wav_file, start=0, end=None):
    """
    Reads data from a wav-file, converts this data to single channel and trims zeros at beginning and end of the
    audio data.
    :param wav_file: path to an existing .wav file
    :return: np array of audio data, frame rate
    """
    sound_info, frame_rate, = sf.read(wav_file)
    # convert stereo to mono
    if len(sound_info.shape) > 1:
        sound_info = sound_info.astype(float)
        sound_info = sound_info.sum(axis=1) / 2
        sound_info = np.array(sound_info)
    # remove zeros at beginning and end of audio file
    sound_info = np.trim_zeros(sound_info)
    start = int(start * frame_rate)
    end = int(end * frame_rate) if end else None
    sound_info = sound_info[start:end] if end else sound_info[start:]
    return sound_info, frame_rate


def plot(wav_file, window, hop, mode='spectrogram', size=227, output_folder=None, wav_folder=None, start=0, end=None,
         nfft=None, **kwargs):
    """
    Plot spectrograms for equally sized chunks of a wav-file using the described parameters.
    :param wav_file: path to an existing .wav file
    :param window: length of the chunks in s.
    :param hop: stepsize for chunking the audio data in s
    :param nfft: number of samples for the fast fourier transformation (Defaukt: 256)
    :param cmap: colourmap for the power spectral density (Default: 'viridis')
    :param size: size of the spectrogram plot in pixels. Height and width are alsways identical (Default: 227)
    :param output_folder: if given, the plot is saved to this existing folder in .png format (Default: None)
    :return: blob of the spectrogram plot
    """
    sound_info, sr = _read_wav_data(wav_file, start=start, end=end)
    if not nfft:
        nfft = _next_power_of_two(int(sr * 0.025))
    write_index = window or hop
    wav_out = join(wav_folder, basename(wav_file)) if wav_folder else None
    for idx, chunk in enumerate(_generate_chunks(sound_info, sr, window, hop, start, wav_out=wav_out)):
        fig = plt.figure(frameon=False)
        fig.set_size_inches(1, 1)
        ax = plt.Axes(fig, [0., 0., 1., 1.], )
        ax.set_axis_off()
        fig.add_axes(ax)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            spectrogram_axes = PLOTTING_FUNCTIONS[mode](chunk, sr, nfft, **kwargs)

        fig.add_axes(spectrogram_axes, id='spectrogram')

        if output_folder:
            file_name = basename(wav_file)[:-4]
            outfile = join(output_folder, '{}_{:.4f}'.format(file_name, start + idx * hop).rstrip('0').rstrip(
                '.') + '.png') if write_index else join(output_folder,
                                                        file_name + '.png')
            fig.savefig(outfile, format='png', dpi=size)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=size)
        buf.seek(0)
        plt.close('all')
        img_blob = buf.read()
        try:
            img = imread_from_blob(img_blob, 'png')
            img = img[:, :, :-1]
        except IOError:
            print('Error while reading the spectrogram blob.')
            return None

        yield img


def plot_spectrogram(audio_data, sr, nfft=None, delta=None, **kwargs):
    spectrogram = librosa.stft(audio_data, n_fft=nfft, hop_length=int(nfft / 2), center=False)
    if delta:
        spectrogram = librosa.feature.delta(spectrogram, order=delta)
    spectrogram = librosa.amplitude_to_db(spectrogram, ref=np.max, top_db=None)
    return _create_plot(spectrogram, sr, nfft, **kwargs)


def plot_mel_spectrogram(audio_data, sr, nfft=None, melbands=64, delta=None, **kwargs):
    spectrogram = librosa.feature.melspectrogram(y=audio_data, sr=sr, n_fft=nfft,
                                                 hop_length=int(nfft / 2),
                                                 n_mels=melbands)
    if delta:
        spectrogram = librosa.feature.delta(spectrogram, order=delta)
    spectrogram = librosa.logamplitude(spectrogram, ref=np.max, top_db=None)
    return _create_plot(spectrogram, sr, nfft, **kwargs)


def plot_chroma(audio_data, sr, nfft=None, delta=None, **kwargs):
    spectrogram = librosa.feature.chroma_stft(audio_data, sr, n_fft=nfft, hop_length=int(nfft / 2))
    if delta:
        spectrogram = librosa.feature.delta(spectrogram, order=delta)
    return _create_plot(spectrogram, sr, nfft, **kwargs)


def _create_plot(spectrogram, sr, nfft, ylim=None, cmap='viridis', scale='linear'):
    if ylim:
        relative_limit = ylim * 2 / sr
        relative_limit = min(relative_limit, 1)
        spectrogram = spectrogram[:int(relative_limit * (1 + nfft / 2)), :]
    spectrogram_axes = librosa.display.specshow(spectrogram, hop_length=int(nfft / 2), sr=sr, cmap=cmap, y_axis=scale)
    return spectrogram_axes


def _generate_chunks(sound_info, sr, window, hop, start=0, wav_out=None):
    if not window and not hop:
        yield sound_info
        return
    window_samples = int(window * sr)
    hop_samples = int(hop * sr)
    for n in range(max(int((len(sound_info)) / hop_samples), 1)):
        chunk = sound_info[n * hop_samples:min(n * hop_samples + window_samples, len(sound_info))]
        if wav_out:
            chunk_out = '{}_{:.4f}'.format(wav_out[:-4], start + n * hop).rstrip('0').rstrip('.') + '.wav'
            sf.write(chunk_out, chunk, sr)
        yield chunk


def _next_power_of_two(x):
    return 1 << (x - 1).bit_length()


PLOTTING_FUNCTIONS = {'spectrogram': plot_spectrogram,
                      'mel': plot_mel_spectrogram, 'chroma': plot_chroma}


def plot_file(file, input_path, output_spectrograms=None, output_wavs=None, **kwargs):
    spectrogram_directory = None
    wav_directory = None
    if output_spectrograms:
        spectrogram_directory = join(output_spectrograms, get_relative_path(file, input_path))
        makedirs(spectrogram_directory, exist_ok=True)
    if output_wavs:
        wav_directory = join(output_wavs, get_relative_path(file, input_path))
        makedirs(wav_directory, exist_ok=True)
    return np.asarray([audio_plot for audio_plot in
                       plot(file, output_folder=spectrogram_directory, wav_folder=wav_directory, **kwargs)])


def get_relative_path(file, prefix):
    filepath = pathlib.PurePath(dirname(file))
    filepath = filepath.relative_to(prefix)

    return str(filepath)


class PlotGenerator():
    def __init__(self, files, input_path, output_spectrograms=None, output_wavs=None, number_of_processes=None,
                 **kwargs):
        # self.input_path = input_path
        # self.output_spectrograms = output_spectrograms
        # self.output_wavs = output_wavs
        # self.file_name_queue = JoinableQueue()
        # for file in files:
        #     self.file_name_queue.put(file)
        #
        # self.plot_queue = JoinableQueue()
        # self.length = len(files)
        self.files = files
        self.number_of_processes = number_of_processes

        if not self.number_of_processes:
            self.number_of_processes = cpu_count()
        plotting_func = partial(
            plot_file, input_path=input_path, output_spectrograms=output_spectrograms, output_wavs=output_wavs,
            **kwargs)

        self.pool =  Pool(processes=self.number_of_processes)
        self.plots = self.pool.imap(plotting_func, self.files)
            # self.processes = []
            # self.finished_processes = Value('i', 0)
            # for i in range(number_of_processes):
            #     p = Process(target=self.plotting_worker, args=self.finished_processes, kwargs=kwargs)
            #     p.daemon = True
            #     self.processes.append(p)
            #     self.file_name_queue.put(None)
            #     p.start()

    def __len__(self):
        return len(self.files)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self.plots)
        except StopIteration:
            self.pool.close()
            raise StopIteration
        # if self.plot_queue.empty() and self.finished_processes.value:
        #     for p in self.processes:
        #         p.join()
        #     self.file_name_queue.close()
        #     self.plot_queue.close()
        #     self.file_name_queue.join()
        #     self.plot_queue.join()
        #     raise StopIteration
        # else:
        #     return self.plot_queue.get()

        # def plotting_worker(self, finished_processes, **kwargs):
        #     # print('Process ' + str(id) + ': ' + 'initializing...')
        #     # wait for all threads to be initialized
        #     try:
        #         while True:
        #             file = self.file_name_queue.get()
        #             if file:
        #                 plots = plot_file(file, input_path=self.input_path, output_spectrograms=self.output_spectrograms,
        #                                   output_wavs=self.output_wavs, **kwargs)
        #                 if plots is not None:
        #                     filename = basename(file)
        #                     self.plot_queue.put((filename, plots))
        #                 self.file_name_queue.task_done()
        #             else:
        #                 self.file_name_queue.task_done()
        #                 with finished_processes.get_lock():
        #                     finished_processes.value += 1
        #                 break
        #     except KeyboardInterrupt:
        #         pass