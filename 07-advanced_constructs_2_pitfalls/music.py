from collections import defaultdict
from math import log2, pow
import numpy
import struct
import sys
import wave

P = 1  # P is the (time) length of the analysis window in seconds
sliding_window = 0.1


def get_pitch_from_frequency(pitch_freq, a4_freq=440):
    # c0 is the first pitch in lowest octave
    # constant 4.75 = (4 * 12 + 9) / 12 - 4 octaves lower + 9 in one octave between a and c
    c0_freq = a4_freq * pow(2, -4.75)
    pitches = ["c", "cis", "d", "es", "e", "f", "fis", "g", "gis", "a", "bes", "b"]

    half_steps, sign_for_cent, cents = get_half_step_sign_cents(pitch_freq, c0_freq)

    octave = half_steps // 12
    pitch_index_in_octave = half_steps % 12
    pitch_in_helmholtz = convert_to_helmholtz(pitches[pitch_index_in_octave], octave)

    return "{0}{1}{2}".format(pitch_in_helmholtz, sign_for_cent, cents)


def get_half_step_sign_cents(freq, c0):
    half_step_float = 12 * log2(freq / c0)
    half_step = round(half_step_float)

    if half_step_float < half_step:
        sign = "-"
        closest_pitch_freq = get_frequency_from_half_step(half_step, c0)
        cents = 12 * 100 * log2(closest_pitch_freq / freq)
    else:
        sign = "+"
        closest_pitch_freq = get_frequency_from_half_step(half_step, c0)
        cents = 12 * 100 * log2(freq / closest_pitch_freq)

    return half_step, sign, round(cents)


def get_frequency_from_half_step(half_steps, c0):
    return pow(2, (half_steps / 12)) * c0


def convert_to_helmholtz(pitch, octave):
    if octave <= 2:
        return pitch.title() + abs(octave - 2) * ","
    else:
        return pitch + (octave - 3) * "’"


def read_wav(file_path):
    with wave.open(file_path, mode="rb") as wav_file:
        channels = wav_file.getnchannels()
        frames = wav_file.getnframes()
        fr = wav_file.getframerate()

        raw_data = wav_file.readframes(nframes=frames)

        wav_file.close()

    wav_iter = struct.iter_unpack("h", raw_data)

    samples = []

    for x in wav_iter:
        if channels == 1:
            samples.append(x[0])
        elif channels == 2:
            y = wav_iter.__next__()
            avg_stereo = (x[0] + y[0]) / 2
            samples.append(avg_stereo)
        else:
            sys.exit("Too many channels.")

    return numpy.array(samples), fr


def generate_chunks(sequence, rate):
    window_size = P * rate
    step = int(round(rate * sliding_window))
    number_of_chunks = (int((len(sequence) - window_size) / step)) + 1

    for i in range(0, number_of_chunks * step, step):
        yield sequence[i:i + window_size]


def get_top_peaks(sample, number_of_peaks=3):
    ft = numpy.fft.rfft(sample)
    amplitudes = numpy.abs(ft)
    average_amplitude = numpy.mean(amplitudes)
    threshold_amplitude = 20 * average_amplitude
    peaks = numpy.argwhere(amplitudes >= threshold_amplitude)
    peaks_indices = [x[0] for x in peaks]
    if not peaks_indices:
        return []

    top_peaks = []
    temp_cluster = []
    old_freq = None

    peaks = sorted([(peak_f, amplitudes[peak_f]) for peak_f in peaks_indices])
    for freq, amplitude in peaks:
        old_freq = freq if not old_freq else old_freq
        if freq - old_freq > 1:
            top_peaks.append(sorted(temp_cluster, key=lambda x: x[1], reverse=True)[0])
            temp_cluster = []
        temp_cluster.append((freq, amplitude))
        old_freq = freq
    top_peaks.append(sorted(temp_cluster, key=lambda x: x[1], reverse=True)[0])

    sorted_peaks = sorted(top_peaks, key=lambda x: x[1], reverse=True)
    return sorted([x[0] for x in sorted_peaks[:3]])


def compose_pitches_from_peaks(peaks, a4_frequency):
    if len(peaks) == 0:
        return "no peaks"

    pitches = []
    for peak in sorted(peaks):
        pitches.append(get_pitch_from_frequency(peak, a4_freq=a4_frequency))

    return " ".join(pitches)


def analyse_wav(data, fr, a4_frequency):

    current_time = 0.0
    pitch_to_time = defaultdict(lambda: defaultdict(list))
    current = 0
    previous_pitch = None

    for chunk in generate_chunks(data, fr):
        current_time += sliding_window
        top_peaks = get_top_peaks(chunk)
        my_pitch = compose_pitches_from_peaks(top_peaks, a4_frequency)

        if my_pitch != previous_pitch:
            current += 1
            previous_pitch = my_pitch
        pitch_to_time[current][my_pitch].append(round(current_time, 1))

    time_to_pitch = defaultdict(str)

    for c, pitch_times in pitch_to_time.items():
        for pitch, all_times in pitch_times.items():
            min_time = round(min(all_times) - sliding_window, 1)
            max_time = max(all_times)
            time_to_pitch["{}-{}".format("%04.1f" % min_time, "%04.1f" % max_time)] = pitch

    for t, p in sorted(time_to_pitch.items()):
        if p == "no peaks":
            continue
        print("{} {}".format(t, p))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit("First argument has to be frequency of a' (A4), second path to valid audio file in wav format!")

    a4_frequency = int(sys.argv[1])
    path_to_wav = sys.argv[2]
    wav_data, frame_rate = read_wav(path_to_wav)
    analyse_wav(wav_data, frame_rate, a4_frequency)
