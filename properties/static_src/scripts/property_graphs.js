import Chart from "chart.js/auto";

const accent = {
  green: "#6b9e78",
  greenBright: "#7db88c",
  greenFill: "rgba(107, 158, 120, 0.35)",
  amber: "#c9a84c",
  amberFill: "rgba(201, 168, 76, 0.35)",
  terracotta: "#c47055",
  terracottaFill: "rgba(196, 112, 85, 0.35)",
  slate: "#7eaab8",
  slateFill: "rgba(126, 170, 184, 0.3)",
  grid: "rgba(107, 158, 120, 0.08)",
  ticks: "#847c72",
};

const backgroundColors = [
  accent.greenFill,
  accent.terracottaFill,
  accent.amberFill,
  accent.slateFill,
  "rgba(221, 215, 205, 0.18)",
  "rgba(160, 152, 144, 0.3)",
  "rgba(107, 158, 120, 0.55)",
  "rgba(196, 112, 85, 0.55)",
  "rgba(201, 168, 76, 0.55)",
  "rgba(126, 170, 184, 0.55)",
];

const borderColors = [
  "rgba(107, 158, 120, 0.9)",
  "rgba(196, 112, 85, 0.9)",
  "rgba(201, 168, 76, 0.9)",
  "rgba(126, 170, 184, 0.9)",
  "rgba(221, 215, 205, 0.5)",
  "rgba(160, 152, 144, 0.7)",
  "rgba(107, 158, 120, 1)",
  "rgba(196, 112, 85, 1)",
  "rgba(201, 168, 76, 1)",
  "rgba(126, 170, 184, 1)",
];

const fontStack = '"Monaspace Argon", Consolas, "Liberation Mono", Monaco, "Courier New", monospace';

Chart.defaults.color = accent.ticks;
Chart.defaults.borderColor = accent.grid;
Chart.defaults.font.family = fontStack;
Chart.defaults.font.size = 11;

const tickFont = { size: 11, family: fontStack };
const legendLabel = { boxWidth: 10, boxHeight: 10, font: tickFont, color: "#d1d8d4" };

document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("chart-response-times");
  if (!canvas) return;
  const data = JSON.parse(
    document.getElementById("chart-status-response-times-data").innerHTML
  );
  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, "rgba(107, 158, 120, 0.35)");
  gradient.addColorStop(1, "rgba(107, 158, 120, 0)");
  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => {
        const date = new Date(d.label);
        return `${date.getHours() % 12 || 12}:${date.getMinutes() < 10 ? "0" : ""}${date.getMinutes()} ${date.getHours() >= 12 ? "PM" : "AM"}`;
      }),
      datasets: [
        {
          label: "Response time (ms)",
          data: data.map((d) => d.count),
          backgroundColor: gradient,
          borderColor: accent.green,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: accent.greenBright,
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 0 },
      plugins: {
        tooltip: {
          mode: "index",
          intersect: false,
          backgroundColor: "rgba(9, 8, 6, 0.95)",
          titleColor: "#ede8e0",
          bodyColor: "#ddd7cd",
          borderColor: "rgba(107, 158, 120, 0.2)",
          borderWidth: 1,
          padding: 10,
          titleFont: tickFont,
          bodyFont: tickFont,
        },
        legend: { position: "top", labels: legendLabel },
      },
      scales: {
        x: {
          grid: { color: accent.grid, drawBorder: false },
          ticks: { autoSkip: true, maxRotation: 25, font: tickFont, color: accent.ticks },
        },
        y: {
          grid: { color: accent.grid, drawBorder: false },
          ticks: {
            beginAtZero: true,
            font: tickFont,
            color: accent.ticks,
            callback: (value) => `${value} ms`,
          },
        },
      },
    },
  });
  chart.canvas.parentNode.style.width = "100%";
  chart.canvas.parentNode.style.height = "300px";
});

function buildDoughnut(canvasId, dataId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const data = JSON.parse(document.getElementById(dataId).innerHTML);
  const ctx = canvas.getContext("2d");

  // Color rule: status 200 / Uptime = moss green, non-200 / Downtime =
  // terracotta, everything else pulls from the earthy palette in order.
  const paint = (label) => {
    const name = String(label || "").toLowerCase();
    if (name === "uptime" || name === "200") return [accent.greenFill, "rgba(107, 158, 120, 0.95)"];
    if (name === "downtime") return [accent.terracottaFill, "rgba(196, 112, 85, 0.95)"];
    return null;
  };

  const bg = data.map((d, i) => {
    const p = paint(d.label);
    return p ? p[0] : backgroundColors[i % backgroundColors.length];
  });
  const bd = data.map((d, i) => {
    const p = paint(d.label);
    return p ? p[1] : borderColors[i % borderColors.length];
  });

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.map((d) => d.label),
      datasets: [
        {
          data: data.map((d) => d.count),
          backgroundColor: bg,
          borderColor: bd,
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      aspectRatio: 2,
      animation: { animateRotate: false },
      cutout: "62%",
      plugins: {
        legend: { position: "right", labels: legendLabel },
        tooltip: {
          backgroundColor: "rgba(9, 8, 6, 0.95)",
          titleColor: "#ede8e0",
          bodyColor: "#ddd7cd",
          borderColor: "rgba(107, 158, 120, 0.2)",
          borderWidth: 1,
          padding: 10,
          titleFont: tickFont,
          bodyFont: tickFont,
        },
      },
    },
  });
}

document.addEventListener("DOMContentLoaded", () => buildDoughnut("chart-status-codes", "chart-status-codes-data"));
document.addEventListener("DOMContentLoaded", () => buildDoughnut("chart-uptime", "chart-uptime-data"));
