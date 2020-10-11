set terminal postscript eps enhanced color font 'Helvetica,16'
set output "comparison.eps"
set key autotitle columnheader left
set xrange [0:36]
set yrange [0:90000]
set ylabel "Cumulative expenditure (EUR)"
set xlabel "Month"
plot for [i=2:12] cumexp u 1:i w lp

unset xrange
set yrange [0:160]
set ylabel "Total daily cost (EUR)\namortized over a 3-year period"
set xlabel "Number of devices"
set output "devices.eps"
plot for [i=2:12] perdevice u 1:i w lp
