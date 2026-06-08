async function loadJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url} yüklenemedi`);
    return response.json();
}

function buildCharts(planData, incomeData) {
    const planCtx = document.getElementById("planChart");
    const incomeCtx = document.getElementById("incomeChart");

    new Chart(planCtx, {
        type: "doughnut",
        data: {
            labels: planData.labels,
            datasets: [{
                data: planData.values,
                backgroundColor: ["#126b5f", "#b84b38", "#345995"],
                borderColor: "#ffffff",
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" }
            }
        }
    });

    new Chart(incomeCtx, {
        type: "bar",
        data: {
            labels: incomeData.labels,
            datasets: [{
                label: "Gelir",
                data: incomeData.values,
                backgroundColor: "#345995",
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => new Intl.NumberFormat("tr-TR").format(value)
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => new Intl.NumberFormat("tr-TR", {
                            style: "currency",
                            currency: "TRY"
                        }).format(ctx.parsed.y)
                    }
                }
            }
        }
    });
}

Promise.all([
    loadJson("/api/dashboard/plan-dagilimi"),
    loadJson("/api/dashboard/aylik-gelir")
])
    .then(([planData, incomeData]) => buildCharts(planData, incomeData))
    .catch((error) => console.error(error));
