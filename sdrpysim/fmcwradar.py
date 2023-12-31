import numpy as np
import matplotlib.pyplot as plt
from numpy import fft
from mpl_toolkits.mplot3d import Axes3D

#ref: https://community.infineon.com/t5/Knowledge-Base-Articles/FMCW-radar-working-principle-simulation-based-on-python-Chapter-1-Distance/ta-p/366803

#Radar parameters setting
maxR = 200 #Maximum range
rangeRes = 1 #Range resolution = c/2B
maxV = 70 #Maximum speed
fc = 77e9 #Carrier frequency
c = 3e8 #Speed of light

r0 = 100 #Target distance
v0 = 70 #Target speed

B = c/(2*rangeRes) #Bandwidth required for 1 meter resolution: 150MHz
Tchirp = 5.5*2*maxR/c #Chirp time 7.3ms
endle_time = 6.3e-6 #6.3ms
slope = B/Tchirp #Chirp slope 150MHz/7.3ms
f_IFmax = (slope*2*maxR)/c #Maximum IF frequency 27.272727MHz for max range
f_IF = (slope*2*r0)/c #Current IF frequency 13.636363MHz for current targe distance

Nd = 128 #Number of chirp
Nr = 1024 #Number ADC sampling points
vres = (c/fc)/(2*Nd*(Tchirp+endle_time)) #Speed resolution 1.11, not used
Fs = Nr/Tchirp #Sampling rate=1024/7.3ms=139.636363M

#TX
t = np.linspace(0,Nd*Tchirp,Nr*Nd) #total time steps of Tx and Rx, 128*1024=131072
angle_freq = fc*t+(slope*t*t)/2 #Tx signal angle speed f=fc+slope*t/2
freq = fc + slope*t #Tx frequency
Tx = np.cos(2*np.pi*angle_freq) #Waveform of Tx (131072,)

plt.subplot(4,2,1)
plt.plot(t[0:1024],Tx[0:1024])
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('Tx Signal')
plt.subplot(4,2,3)
plt.plot(t[0:1024],freq[0:1024])
plt.xlabel('Time')
plt.ylabel('Frequency')
plt.title('Tx F-T')

r0 = r0+v0*t

#RX
td = 2*r0/c #(131072,)
tx = t
freqRx = fc + slope*(t) #the same to freq
Rx = np.cos(2*np.pi*(fc*(t-td) + (slope*(t-td)*(t-td))/2)) #(131072,)

plt.subplot(4,2,2)
plt.plot(t[0:1024],Rx[0:1024])
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('Rx Signal')
plt.subplot(4,2,3)
plt.plot(t[0:1024]+td[0:1024],freqRx[0:1024])
plt.xlabel('Time')
plt.ylabel('Frequency')
plt.title('Chirp F-T')

# IF signal can be represented by cos((2*pi*wt*t-2*pi*wr*t)),
IF_angle_freq = fc*t+(slope*t*t)/2 - ((fc*(t-td) + (slope*(t-td)*(t-td))/2)) #(131072,)
freqIF = slope*td #(131072,)
IFx = np.cos(-(2*np.pi*(fc*(t-td) + (slope*(t-td)*(t-td))/2))+(2*np.pi*angle_freq)) #(131072,)

plt.subplot(4,2,4)
plt.plot(t[0:1024],IFx[0:1024])
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('IFx Signal')

#Range FFT
doppler = 10*np.log10(np.abs(np.fft.fft(IFx[0:1024]))) #(1024,)
frequency = np.fft.fftfreq(1024, 1/Fs)
range = frequency*c/(2*slope)
plt.subplot(4,2,5)
plt.plot(range[0:512],doppler[0:512])
plt.xlabel('Frequency->Distance')
plt.ylabel('Amplitude')
plt.title('IF Signal FFT')

#2D plot
plt.subplot(4,2,6)
plt.specgram(IFx,1024,Fs)
plt.xlabel('Time')
plt.ylabel('Frequency')
plt.title('Range-Frequency Spectogram')

plt.tight_layout(pad=3, w_pad=0.05, h_pad=0.05)
plt.show()


#Speed Calculate
#Extract one sampling point per chirp, for a frame with 128 chirp, there will be a list of 128 points.
chirpamp = []
chirpnum = 1
while(chirpnum<=Nd): #Nd=128 all chirps
    strat = (chirpnum-1)*1024 #starting index
    end = chirpnum*1024
    chirpamp.append(IFx[(chirpnum-1)*1024])
    chirpnum = chirpnum + 1
#Speed Dimension FFT for Phase difference  and Velocity 速度维做FFT得到相位差
doppler = 10*np.log10(np.abs(np.fft.fft(chirpamp))) #(128,)
FFTfrequency = np.fft.fftfreq(Nd,1/Fs)
velocity = 5*np.arange(0,Nd)/3
#plt.subplot(4,2,7)
plt.figure(figsize=(10,6))
plt.plot(velocity[0:int(Nd/2)],doppler[0:int(Nd/2)])
plt.xlabel('Velocity')
plt.ylabel('Amplitude')
plt.title('IF Velocity FFT')
plt.show()

#2D plot
mat2D = np.zeros((Nd, Nr)) #128 chirps * 1024 samples/chirp
i = 0
while(i<Nd):
    mat2D[i, :] = IFx[i*1024:(i+1)*1024]
    i = i + 1
plt.figure(figsize=(10,6))
plt.matshow(mat2D)
plt.title('Original data')

#2D FFT and Velocity-Distance Relationship
Z_fft2 = abs(np.fft.fft2(mat2D)) #(128, 1024)
Data_fft2 = Z_fft2[0:64,0:512] #get half
#plt.subplot(4,2,8)
plt.figure(figsize=(10,6))
plt.imshow(Data_fft2) #(64, 512)
plt.xlabel("Range")
plt.ylabel("Velocity")
plt.title('Velocity-Range 2D FFT')

plt.tight_layout(pad=3, w_pad=0.05, h_pad=0.05)
plt.show()