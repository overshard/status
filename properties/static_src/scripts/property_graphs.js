import Chart from "chart.js/auto";

const backgroundColors = [
  "rgba(13, 110, 253, 0.4)",
  "rgba(102, 16, 242, 0.4)",
  "rgba(111, 66, 193, 0.4)",
  "rgba(214, 51, 132, 0.4)",
  "rgba(220, 53, 69, 0.4)",
  "rgba(253, 126, 20, 0.4)",
  "rgba(255, 193, 7, 0.4)",
  "rgba(25, 135, 84, 0.4)",
  "rgba(32, 201, 151, 0.4)",
  "rgba(13, 202, 240, 0.4)",
];

const fontStack = 'Consolas, "Andale Mono WT", "Andale Mono", "Lucida Console", "Lucida Sans Typewriter", "DejaVu Sans Mono", "Bitstream Vera Sans Mono", "Liberation Mono", "Nimbus Mono L", Monaco, "Courier New", Courier, monospace';

document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("chart-response-times");
  if (!canvas) return;
  const data = JSON.parse(
    document.getElementById("chart-status-response-times-data").innerHTML
  );
  const ctx = canvas.getContext("2d");
  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => {
        const date = new Date(d.label);
        return `${date.getHours() % 12 || 12}:${date.getMinutes() < 10 ? "0" : ""}${date.getMinutes()} ${date.getHours() >= 12 ? "PM" : "AM"}`;
      }),
      datasets: [
        {
          label: "Response times (ms)",
          data: data.map((d) => d.count),
          backgroundColor: "rgba(13, 110, 253, 0.4)",
          borderColor: "rgba(13, 110, 253, 0.8)",
          borderWidth: 3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 0,
      },
      plugins: {
        tooltip: {
          mode: "index",
          intersect: false,
        },
        legend: {
          position: "top",
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            font: {
              size: 12,
              family: fontStack,
            },
          },
        },
      },
      scales: {
        xAxes: {
          ticks: {
            autoSkip: true,
            font: {
              size: 12,
              family: fontStack,
            },
            maxRotation: 25,
          },
        },
        yAxes: {
          ticks: {
            beginAtZero: true,
            font: {
              size: 12,
              family: fontStack,
            },
            callback: function(value, index, ticks) {
              return `${value} ms`;
            }
          },
        },
      },
    },
  });
  chart.canvas.parentNode.style.width = "100%";
  chart.canvas.parentNode.style.height = "300px";
});

document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("chart-status-codes");
  if (!canvas) return;
  const data = JSON.parse(
    document.getElementById("chart-status-codes-data").innerHTML
  );
  const ctx = canvas.getContext("2d");
  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.map((d) => d.label),
      datasets: [
        {
          data: data.map((d) => d.count),
          backgroundColor: backgroundColors,
          borderColor: backgroundColors,
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      aspectRatio: 2,
      animation: {
        animateRotate: false,
      },
      plugins: {
        legend: {
          position: "right",
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            font: {
              size: 12,
              family: fontStack,
            },
          },
        },
      },
    },
  });
});

document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("chart-uptime");
  if (!canvas) return;
  const data = JSON.parse(
    document.getElementById("chart-uptime-data").innerHTML
  );
  const ctx = canvas.getContext("2d");
  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.map((d) => d.label),
      datasets: [
        {
          data: data.map((d) => d.count),
          backgroundColor: backgroundColors,
          borderColor: backgroundColors,
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      aspectRatio: 2,
      animation: {
        animateRotate: false,
      },
      plugins: {
        legend: {
          position: "right",
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            font: {
              size: 12,
              family: fontStack,
            },
          },
        },
      },
    },
  });
});
