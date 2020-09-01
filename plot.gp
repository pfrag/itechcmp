set terminal postscript eps enhanced color font 'Helvetica,16'
set output "comparison.eps"
set key autotitle columnheader

#plot "out" u 1:2 w lp t "LoRaWAN (all-in-one)", "out" u 1:3 w lp t "LoRaWAN (cloud-based)", "out" u 1:4 w lp t "NB-IoT (monthly fees)", "out" u 1:5 w lp t "NB-IoT (flat rate, unlimited)"
plot for [i=2:12] 'out' u 1:i w lp
