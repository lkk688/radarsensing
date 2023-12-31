import time
from time import sleep
import adi
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from timeit import default_timer as timer
import phaser.mycn0566 as mycn0566
CN0566=mycn0566.CN0566
import pickle

# Read back properties from hardware https://analogdevicesinc.github.io/pyadi-iio/devices/adi.ad936x.html
def printSDRproperties(sdr):
    print("Bandwidth of TX path:", sdr.tx_rf_bandwidth) #Bandwidth of front-end analog filter of TX path
    print("Loopback:", sdr.loopback) #0: disable, 1: Digital TX → Digital RX, 2: RF RX → RF TX
    print("TX gain chan0:", sdr.tx_hardwaregain_chan0) #Attenuation applied to TX path, -30
    print("TX gain chan1:", sdr.tx_hardwaregain_chan1) #Attenuation applied to TX path, -10
    print("TX enabled channels:", sdr.tx_enabled_channels) 
    print("RX enabled channels:", sdr.rx_enabled_channels)
    print("RX buffer size:", sdr.rx_buffer_size) #1024

    print("TX LO: %s" % (sdr.tx_lo)) #Carrier frequency of TX path
    print("RX LO: %s" % (sdr.rx_lo)) #Carrier frequency of RX path
    print("AGC Mode chan0:", sdr.gain_control_mode_chan0)
    print("AGC Mode chan1:", sdr.gain_control_mode_chan1)#Mode of receive path AGC. Options are: slow_attack, fast_attack, manual
    print("RX gain chan0:", sdr.rx_hardwaregain_chan0)#71
    print("RX gain chan1:", sdr.rx_hardwaregain_chan1)#71 Gain applied to RX path. Only applicable when gain_control_mode is set to ‘manual’
    print("rx_rf_bandwidth:", sdr.rx_rf_bandwidth) #4Mhz Bandwidth of front-end analog filter of RX path
    print("Sample rate:", sdr.sample_rate) #Sample rate RX and TX paths in samples per second
    print("DDS scales:", sdr.dds_scales)

def initPhaser(urladdress, my_sdr, calibrationfile=True, Blackman=False):
    #my_phaser = adi.CN0566(uri=urladdress, sdr=my_sdr)
    my_phaser = CN0566(uri=urladdress, sdr=my_sdr)
    print("Phaser url: ", my_phaser.uri)
    print("Phaser already connected")

    # Initialize both ADAR1000s, set gains to max, and all phases to 0
    #load calibration files
    my_phaser.configure(device_mode="rx")

    my_phaser.freq_dev_step = 5690
    my_phaser.freq_dev_range = 0
    my_phaser.freq_dev_time = 0
    my_phaser.powerdown = 0
    my_phaser.ramp_mode = "disabled"

    # Averages decide number of time samples are taken to plot and/or calibrate system. By default it is 1.
    my_phaser.Averages = 4

    if calibrationfile:
        updatePhaserCalibration(my_phaser, calibrationfile=True, gain=64, Blackman=Blackman)

    return my_phaser

def updatePhaserCalibration(my_phaser, calibrationfile=False, rxgain=30, gain=64, Blackman=False):
    if calibrationfile:
        my_phaser.load_gain_cal() #gcal
        my_phaser.load_phase_cal() #pcal
        my_phaser.load_channel_cal() #ccal for channels 0 and 1
    for i in range(0, 8):
        my_phaser.set_chan_phase(i, 0) #apply channel phase calibration for rx_phase

    if Blackman == True:
        gain_list = [8, 34, 84, 127, 127, 84, 34, 8]  # Blackman taper
        for i in range(0, len(gain_list)):
            my_phaser.set_chan_gain(i, gain_list[i], apply_cal=True)
    else:
        # Set all antenna elements to half scale - a typical HB100 will have plenty of signal power.
        #gain = 64 # 64 is about half scale
        for i in range(8):
            my_phaser.set_chan_gain(i, gain, apply_cal=True) #rx_gain
    
    #apply channel calibration for two SDR channels
    # First crack at compensating for channel gain mismatch
    my_phaser.sdr.rx_hardwaregain_chan0 = (
        #my_phaser.sdr.rx_hardwaregain_chan0 + my_phaser.ccal[0]
        rxgain + my_phaser.ccal[0]
    )
    my_phaser.sdr.rx_hardwaregain_chan1 = (
        #my_phaser.sdr.rx_hardwaregain_chan1 + my_phaser.ccal[1]
        rxgain + my_phaser.ccal[1]
    )

colors = ["black", "gray", "red", "orange", "yellow", "green", "blue", "purple"]
from phaser.phaser_functions import (
    calculate_plot,
    channel_calibration,
    gain_calibration,
    load_hb100_cal,
    phase_calibration,
)
def calibratePhaser(my_phaser, savefile=False):
    my_phaser.set_beam_phase_diff(0.0)
    channel_calibration(my_phaser, verbose=True)
    print(my_phaser.ccal)

    if savefile == True:
        my_phaser.save_channel_cal(filename="channel_cal.pkl")
        print("Calibrating Gain, verbosely, then saving cal file...")

    # Start Gain Calibration
    my_phaser.set_beam_phase_diff(0.0)
    #    plot_data = my_phaser.gain_calibration(verbose=True)  # Start Gain Calibration
    plot_data = gain_calibration(my_phaser, verbose=True)  # Start Gain Calibration
    print(my_phaser.gcal)
    plt.figure(figsize=(10,6))
    plt.title("Gain calibration FFTs")
    plt.xlabel("FFT Bin number")
    plt.ylabel("Amplitude (ADC counts)")
    for i in range(0, 8):
        plt.plot(plot_data[i], color=colors[i])
    plt.show()
    if savefile == True:
        my_phaser.save_gain_cal(filename="gain_cal.pkl")  # Default filename
        print("Calibrating Phase, verbosely, then saving cal file...")
    
    # Start Phase Calibration
    PhaseValues, plot_data = phase_calibration(
        my_phaser, verbose=True
    )  # Start Phase Calibration
    print(my_phaser.pcal)
    plt.figure(figsize=(10,6))
    plt.title("Phase sweeps of adjacent elements")
    plt.xlabel("Phase difference (degrees)")
    plt.ylabel("Amplitude (ADC counts)")
    for i in range(0, 7):
        plt.plot(PhaseValues, plot_data[i], color=colors[i])
    plt.show()
    if savefile == True:
        my_phaser.save_phase_cal(filename="phase_cal.pkl")  # Default filename
    
    #updatePhaserCalibration(my_phaser, calibrationfile=False, gain=64, Blackman=False)
    print("Done calibration")

def configureADF4159(my_phaser, output_freq= 12.1e9, BW= 500e6, num_steps= 1000, ramp_time= 1e3):
    # Configure the ADF4159 Rampling PLL
    #final output is 12.1GHz-LO(2.1GHz)=10GHz, Ramp range is 10GHz~10.5Ghz(10GHz+500MHz)
    # output_freq = 12.1e9 
    # BW = 500e6
    # num_steps = 1000
    # ramp_time = 1e3  # us
    ramp_time_s = ramp_time / 1e6
    my_phaser.frequency = int(output_freq / 4)  # Output frequency divided by 4, there is /4 ahead of the ADF4159 RFIN
    my_phaser.freq_dev_range = int(
        BW / 4
    )  # frequency deviation range in Hz.  This is the total freq deviation of the complete freq ramp
    my_phaser.freq_dev_step = int(
        BW / num_steps
    )  # frequency deviation step in Hz.  This is fDEV, in Hz.  Can be positive or negative
    my_phaser.freq_dev_time = int(
        ramp_time
    )  # total time (in us) of the complete frequency ramp
    my_phaser.delay_word = 4095  # 12 bit delay word.  4095*PFD = 40.95 us.  For sawtooth ramps, this is also the length of the Ramp_complete signal
    my_phaser.delay_clk = "PFD"  # can be 'PFD' or 'PFD*CLK1'
    my_phaser.delay_start_en = 0  # delay start
    my_phaser.ramp_delay_en = 0  # delay between ramps.
    my_phaser.trig_delay_en = 0  # triangle delay
    my_phaser.ramp_mode = "continuous_triangular"  # ramp_mode can be:  "disabled", "continuous_sawtooth", "continuous_triangular", "single_sawtooth_burst", "single_ramp_burst"
    my_phaser.sing_ful_tri = (
        0  # full triangle enable/disable -- this is used with the single_ramp_burst mode
    )
    my_phaser.tx_trig_en = 0  # start a ramp with TXdata
    my_phaser.enable = 0  # 0 = PLL enable.  Write this last to update all the registers
    return my_phaser

def initAD9361(urladdress, fs, center_freq=2.2e9, rxbuffer=1024, Rx_CH=2, Tx_CH=2, rxbw=4000000, rxgain0=30, rxgain1=30, txgain0=-88, txgain1=-88):
    # Create radio
    sdr = adi.ad9361(uri=urladdress)
    sdr.rx_rf_bandwidth = int(rxbw) #4000000 #4MHz
    sdr.sample_rate = int(fs) 

    # Configure Rx
    #sdr.rx_enabled_channels = [0, 1]  # enable Rx1 (voltage0) and Rx2 (voltage1)
    # Configuration data channels
    if Rx_CH==2:
        sdr.rx_enabled_channels = [0,1] #enable two rx channel
        sdr.gain_control_mode_chan0 = "manual"  # manual or slow_attack
        sdr.gain_control_mode_chan1 = "manual"  # manual or slow_attack
        sdr.rx_hardwaregain_chan0 = int(rxgain0)  # must be between -3 and 70
        sdr.rx_hardwaregain_chan1 = int(rxgain1)  # must be between -3 and 70
    else:
        sdr.rx_enabled_channels = [0] #enables Rx0
        sdr.gain_control_mode_chan0 = "manual"  # manual or slow_attack
        sdr.rx_hardwaregain_chan0 = int(30)  # must be between -3 and 70
    sdr.rx_buffer_size = int(rxbuffer)
    sdr.rx_lo = int(center_freq)  # set this to output_freq - (the freq of the HB100)
    #num_samps = 1024*100#10000 # number of samples returned per call to rx()
    #sdr.rx_buffer_size = num_samps

    #from mycn0566 SDR_init, LKK: these will cause sdr parameters to reset
    # sdr._ctrl.debug_attrs[
    #     "adi,frequency-division-duplex-mode-enable"
    # ].value = "1"  # set to fdd mode
    # sdr._ctrl.debug_attrs[
    #     "adi,ensm-enable-txnrx-control-enable"
    # ].value = "0"  # Disable pin control so spi can move the states
    # sdr._ctrl.debug_attrs["initialize"].value = "1"
    # sdr._rxadc.set_kernel_buffers_count(
    #     1
    # )  # Default is 4 Rx buffers are stored, but we want to change and immediately measure the result, so buffers=1

    # Configure Tx
    if Tx_CH==2:
        sdr.tx_enabled_channels = [0, 1]
        sdr.tx_hardwaregain_chan0 = txgain0  # must be between 0 and -88
        sdr.tx_hardwaregain_chan1 = txgain1  # must be between 0 and -88
    else:
        sdr.tx_enabled_channels = [0] #enables Tx0
        sdr.tx_hardwaregain_chan0 = txgain0  # must be between 0 and -88
    sdr.tx_cyclic_buffer = True  # must set cyclic buffer to true for the tdd burst mode.  Otherwise Tx will turn on and off randomly
    sdr.tx_lo = int(center_freq)
    # Enable TDD logic in pluto (this is for synchronizing Rx Buffer to ADF4159 TX input)
    # gpio = adi.one_bit_adc_dac(sdr_ip)
    # gpio.gpio_phaser_enable = True

    return sdr
    
def createcomplexsinusoid(fs, signal_freq = 100000, N = 1024):
    # Create a complex sinusoid
    #fc = 3000000
    #N = 1024 #rx buffer size
    #fs = int(sdr.tx_sample_rate)
    ts = 1 / float(fs)
    fc = int(signal_freq / (fs / N)) * (fs / N) #100KHz
    t = np.arange(0, N * ts, ts)
    i = np.cos(2 * np.pi * t * fc) * 2 ** 14
    q = np.sin(2 * np.pi * t * fc) * 2 ** 14
    iq = i + 1j * q
    return iq

def readiio(sdr):
    phy = sdr.ctx.find_device("ad9361-phy")
    # Read product ID register
    pi = phy.reg_read(0x37)
    #print(f"ID: {hex(pi)}")
    r = 0x80000088
    status = phy.reg_read(r)
    if status & 0b0100:
        print("Overflow")

def plotdualchtimefreq(data0, data1, sample_rate):
    # Take FFT
    PSD0 = 10*np.log10(np.abs(np.fft.fftshift(np.fft.fft(data0)))**2)
    PSD1 = 10*np.log10(np.abs(np.fft.fftshift(np.fft.fft(data1)))**2)
    f = np.linspace(-sample_rate/2, sample_rate/2, len(data0))

    # Time plot helps us check that we see the HB100 and that we're not saturated (ie gain isnt too high)
    plt.figure(figsize=(10,6))
    plt.subplot(2, 1, 1)
    plt.plot(data0.real) # Only plot real part
    plt.plot(data1.real)
    plt.xlabel("Data Point")
    plt.ylabel("ADC output")

    # PSDs show where the HB100 is and verify both channels are working
    plt.subplot(2, 1, 2)
    plt.plot(f/1e6, PSD0)
    plt.plot(f/1e6, PSD1)
    plt.xlabel("Frequency [MHz]")
    plt.ylabel("Signal Strength [dB]")
    plt.tight_layout()
    plt.show()

def performbeamforming(phaser, phase_cal,signal_freq):
    powers = [] # main DOA result
    angle_of_arrivals = []
    for phase in np.arange(-180, 180, 2): # sweep over angle
        print(phase)
        # set phase difference between the adjacent channels of devices
        for i in range(8):
            channel_phase = (phase * i + phase_cal[i]) % 360.0 # Analog Devices had this forced to be a multiple of phase_step_size (2.8125 or 360/2**6bits) but it doesn't seem nessesary
            phaser.elements.get(i + 1).rx_phase = channel_phase
        phaser.latch_rx_settings() # apply settings

        steer_angle = np.degrees(np.arcsin(max(min(1, (3e8 * np.radians(phase)) / (2 * np.pi * signal_freq * phaser.element_spacing)), -1))) # arcsin argument must be between 1 and -1, or numpy will throw a warning
        # If you're looking at the array side of Phaser (32 squares) then add a *-1 to steer_angle
        angle_of_arrivals.append(steer_angle)
        data = phaser.sdr.rx() # receive a batch of samples
        data_sum = data[0] + data[1] # sum the two subarrays (within each subarray the 4 channels have already been summed)
        power_dB = 10*np.log10(np.sum(np.abs(data_sum)**2))
        powers.append(power_dB)
        # in addition to just taking the power in the signal, we could also do the FFT then grab the value of the max bin, effectively filtering out noise, results came out almost exactly the same in my tests
        #PSD = 10*np.log10(np.abs(np.fft.fft(data_sum * np.blackman(len(data_sum))))**2) # in dB

    powers -= np.max(powers) # normalize so max is at 0 dB, 180 items
    plt.figure(figsize=(10,6))
    plt.plot(angle_of_arrivals, powers, '.-')
    plt.xlabel("Angle of Arrival")
    plt.ylabel("Magnitude [dB]")
    plt.show()

    # Polar plot
    #plt.figure(figsize=(10,6))
    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(10,6))
    ax.plot(np.deg2rad(angle_of_arrivals), powers) # x axis in radians
    ax.set_rticks([-40, -30, -20, -10, 0])  # Less radial ticks
    ax.set_thetamin(np.min(angle_of_arrivals)) # in degrees
    ax.set_thetamax(np.max(angle_of_arrivals))
    ax.set_theta_direction(-1) # increase clockwise
    ax.set_theta_zero_location('N') # make 0 degrees point up
    ax.grid(True)
    plt.show()

def plotperiodogram(ch0, ch1, fs, my_phaser):
    #https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html
    f, Pxx_den0 = signal.periodogram(
        ch0[1:-1], fs, "blackman", scaling="spectrum"
    )
    f, Pxx_den1 = signal.periodogram(
        ch1[1:-1], fs, "blackman", scaling="spectrum"
    )
    plt.figure(figsize=(10,6))
    plt.clf()
    plt.plot(np.real(ch0), color="red")
    plt.plot(np.imag(ch0), color="blue")
    plt.plot(np.real(ch1), color="green")
    plt.plot(np.imag(ch1), color="black")
    plt.xlabel("data point")
    plt.ylabel("output code")
    plt.draw()

    plt.figure(figsize=(10,6))
    plt.clf()
    plt.semilogy(f, Pxx_den0)
    plt.semilogy(f, Pxx_den1)
    plt.ylim([1e-5, 1e6])
    plt.xlabel("frequency [Hz]")
    plt.ylabel("PSD [V**2/Hz]")
    plt.draw()

    # Plot the output based on experiment that you are performing
    print("Plotting...")

    plt.figure(figsize=(10,6))
    plt.ion()
    #    plt.show()
    (
        gain,#128 array
        angle,#128 array
        delta,#128 array
        diff_error,
        beam_phase,
        xf,
        max_gain,
        PhaseValues,
    ) = calculate_plot(my_phaser)
    #print("Sweeping took this many seconds: " + str(time.time() - start))
    #    gain,  = my_phaser.plot(plot_type="monopulse")
    plt.clf()
    plt.scatter(angle, gain, s=10)
    plt.scatter(angle, delta, s=10)
    plt.show()

    plt.pause(0.05)

def main():
    args = parser.parse_args()
    phaserurladdress = args.phaserurladdress #urladdress #"ip:pluto.local"
    ad9361urladdress = args.ad9361urladdress
    Rx_CHANNEL = args.rxch
    Tx_CHANNEL = args.txch
    calibrate = args.calibrate
    signal_type = args.signal
    plot_flag = args.plot
    
    # Configure properties
    #fs= 6000000 #6MHz
    sample_rate = 6e6 #30e6 #0.6e6 #0.6M
    center_freq = 2.2e9 #2.1e9 #2.1G
    signal_freq = pickle.load(open("./sdradi/phaser/hb100_freq_val.pkl", "rb")) #100e3 #100K
    print("signal_freq:", signal_freq)
    num_slices = 200
    fft_size=1024
    rxbuffersize = 1024*100 # * 16 rx buffer size # samples per buffer
    #img_array = np.zeros((num_slices, fft_size))
    rxbw=4e6 #10e6 #4000000 # analog filter bandwidth
    rxgain=30
    
    sdr=initAD9361(ad9361urladdress, sample_rate, center_freq, rxbuffer=rxbuffersize, \
                   Rx_CH=Rx_CHANNEL, Tx_CH=Tx_CHANNEL, rxbw=rxbw, rxgain0=rxgain, rxgain1=rxgain, txgain0=-88, txgain1=0)

    sleep(1)
    if calibrate: 
        calibrationfile=False
    else:
        calibrationfile=True
    my_phaser=initPhaser(phaserurladdress, sdr, calibrationfile=calibrationfile, Blackman=False)
    my_phaser.SignalFreq = signal_freq
    # Set the Phaser's PLL (the ADF4159 onboard) to downconvert the HB100 to 2.2 GHz plus a small offset
    offset = 1000000 # add a small arbitrary offset just so we're not right at 0 Hz where there's a DC spike
    phaserlo = int(signal_freq + sdr.rx_lo - offset) #10.4+2.2-
    print("Phaser lo:", phaserlo) #12.589GHz
    my_phaser.lo = phaserlo
    
    # Aim the beam at boresight (zero degrees)
    my_phaser.set_beam_phase_diff(0.0)

    if calibrate:
        calibratePhaser(my_phaser, savefile=False)
        updatePhaserCalibration(my_phaser, calibrationfile=calibrationfile, rxgain=rxgain, gain=64, Blackman=False)

        # Configure the ADF4159 Rampling PLL
    #final output is 12.1GHz-LO(2.1GHz)=10GHz, Ramp range is 10GHz~10.5Ghz(10GHz+500MHz)
    # output_freq = 12.1e9 
    # BW = 500e6
    # num_steps = 1000
    # ramp_time = 1e3  # us
    # ramp_time_s = ramp_time / 1e6
    # my_phaser=configureADF4159(my_phaser, output_freq, BW, num_steps, ramp_time)

    # Read properties
    print("RX LO %s" % (sdr.rx_lo)) #2Ghz
    sdr.rx_lo = int(2.2e9) # 2.2GHz The Pluto will tune to this freq
    printSDRproperties(sdr)


    fs = int(sdr.sample_rate) 
    print("sample_rate:", fs)
    N = int(sdr.rx_buffer_size)

    # Grab some samples (whatever we set rx_buffer_size to), remember we are receiving on 2 channels at the same time
    if plot_flag:
        for i in range(3):
            data = sdr.rx()
            data0=data[0]
            data1=data[1]
            plotdualchtimefreq(data0[0:fft_size],data1[0:fft_size], sample_rate)

    #Performing Beamforming
    if calibrate:
        phase_cal = my_phaser.pcal
    else:
        phase_cal = pickle.load(open("./sdradi/phaser/phase_cal_val.pkl", "rb"))
    if plot_flag:
        performbeamforming(my_phaser, phase_cal, signal_freq)
    

    # Collect data
    alldata0 = np.empty(0, dtype=np.complex_) #Default is numpy.float64.
    rxtime=[]
    processtime=[]
    Nperiod=int(5*fs/rxbuffersize) #total time 10s *fs=total samples /fft_size = Number of frames
    print("Total period for 5s:", Nperiod) #73
    my_phaser.set_beam_phase_diff(0.0)

    for r in range(Nperiod):
        start = timer()
        x = sdr.rx() #1024 size array of complex
        rxt = timer()
        timedelta=rxt-start
        rxtime.append(timedelta)
        if Rx_CHANNEL==2:
            data0=x[0]
            data1=x[1]
            data = data0 + data1
        else:
            data=x
        datarate=len(data.real)*4/timedelta/1e6 #Mbps, complex data is 4bytes
        print("Data rate at ", datarate, "Mbps.") #7-8Mbps in 10240 points, 10Mbps in 102400points, single channel in 19-20Mbps
        alldata0 = np.concatenate((alldata0, data))

        if plot_flag:
            plotperiodogram(data0[0:fft_size], data1[0:fft_size], fs, my_phaser)

        readiio(sdr)
        endtime = timer()
        processtime.append(endtime-start)
    
        # Stop transmitting
    sdr.tx_destroy_buffer() #Clears TX buffer
    sdr.rx_destroy_buffer() #Clears RX buffer
    with open('./data/phaser1101data1.npy', 'wb') as f:
        np.save(f, alldata0)
    print(len(alldata0)) #1196032
    
# piuri="ip:phaser.local:50901"#connect ad9361 via Pi
# localuri="ip:analog.local"#Pi
# phaseruri="ip:phaser.local" #CN0566 in pi
# antsdruri="ip:192.168.1.10"#connected via Ethernet with static IP
# plutodruri="ip:192.168.2.16"#connected via USB
#ip:pluto.local
import argparse
parser = argparse.ArgumentParser(description='MyPhaser')
parser.add_argument('--ad9361urladdress', default="ip:pluto.local", type=str,
                    help='urladdress of the device') #ip:pluto.local, ip:phaser.local:50901
parser.add_argument('--phaserurladdress', default="ip:phaser.local", type=str,
                    help='urladdress of the device')
parser.add_argument('--rxch', default=2, type=int, 
                    help='number of rx channels')
parser.add_argument('--txch', default=2, type=int, 
                    help='number of tx channels')
parser.add_argument('--signal', default="dds", type=str,
                    help='signal type: sinusoid, dds')
parser.add_argument('--plot', default=False, type=bool,
                    help='plot figure')
parser.add_argument('--calibrate', default=False, type=bool,
                    help='calibrate')
if __name__ == '__main__':
    main()