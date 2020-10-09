set terminal postscript eps enhanced color font 'Helvetica,16'
set output "comparison.eps"
set key autotitle columnheader left
set xrange [0:36]
set ylabel "Cumulative expenditure (EUR)"
set xlabel "Month"
plot for [i=2:12] cumexp u 1:i w lp

unset xrange
set ylabel "Total daily cost (EUR)\namortized over a 3-year period"
set xlabel "Number of devices"
set output "devices.eps"
plot for [i=2:12] perdevice u 1:i w lp
