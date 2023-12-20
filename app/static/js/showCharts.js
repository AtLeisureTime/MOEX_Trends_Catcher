function drawChart(elem, inputData, myTitle) {
    // Initialize the echarts instance based on the prepared dom
    let myChart = echarts.init(elem); 

    // Specify the configuration items and data for the chart
    const upColor = '#00da3c';
    const upBorderColor = '#008F28';
    const downColor = '#ec0000';
    const downBorderColor = '#8A0000';
    const data = transformData(inputData);

    option = {
        dataset: {
            source: data
        },
        title: {
            text: myTitle
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'line'
            }
        },
        toolbox: {
            feature: {
                dataZoom: {
                    yAxisIndex: false
                }
            }
        },
        grid: [
        {
            left: '15%',
            right: '1%',
            bottom: 150
        },
        {
            left: '15%',
            right: '1%',
            height: 80,
            bottom: 50
        }
        ],
        xAxis: [
            {
                type: 'category',
                boundaryGap: false,
                // inverse: true,
                axisLine: { onZero: false },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            },
            {
                type: 'category',
                gridIndex: 1,
                boundaryGap: false,
                axisLine: { onZero: false },
                axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            }
        ],
        yAxis: [
        {
            scale: true,
                splitArea: {
                show: true
            }
        },
        {
            scale: true,
            gridIndex: 1,
            splitNumber: 2,
            axisLabel: { show: false },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: false }
        }
        ],
        dataZoom: [
        {
            type: 'inside',
            xAxisIndex: [0, 1],
            start: 0,
            end: 100
        },
        {
            show: true,
            xAxisIndex: [0, 1],
            type: 'slider',
            bottom: 10,
            start: 10,
            end: 100
        }
        ],
        visualMap: {
            show: false,
            seriesIndex: 1,
            dimension: 6, // Sign index
            pieces: [
                {
                value: 1,
                color: upColor
                },
                {
                value: -1,
                color: downColor
                }
            ]
        },
        series: [
        {
            type: 'candlestick',
            itemStyle: {
                color: upColor,
                color0: downColor,
                borderColor: upBorderColor,
                borderColor0: downBorderColor
            },
            encode: {
                x: 0,
                y: [1, 4, 3, 2] // OCLH
            }
        },
        {
            name: 'Volume',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            itemStyle: {
                color: '#7fbe9e'
            },
            large: true,
            encode: {
                x: 0,
                y: 5 // Volume
            }
        }
        ]
    };
    // Display the chart using the configuration items and data just specified.
    myChart.setOption(option);
    return myChart;
}

function getSign(data, dataIndex, openVal, closeVal, closeDimIdx) {
    var sign;
    if (openVal > closeVal) {
        sign = -1;
    } else if (openVal < closeVal) {
        sign = 1;
    } else {
        sign =
        dataIndex > 0
            ? // If close === open, compare with close of last record
            data[dataIndex - 1][closeDimIdx] <= closeVal
            ? 1
            : -1
            : // No record of previous, set to be positive
            1;
    }
    return sign;
}

function transformData(inputData) {
    let data = [];    
    for (let i = 0; i < inputData.length; i++) {
        // 'begin'(date), OHLCV
        data[i] = [
            inputData[i][6],
            inputData[i][0],//.toFixed(2),
            inputData[i][2],
            inputData[i][3],
            inputData[i][1],
            inputData[i][5],
            getSign(inputData, i, inputData[i][0], inputData[i][1], 1)
        ];
    }        
    return data;
}

function loadCharts(url) {
    let container = document.getElementById('charts-container');
    let spinner = document.getElementById('spinner');    

    fetch(url)
        .then(response => response.json())
        .then(resp => {            
            container.innerHTML = resp['html'];
            const charts = document.querySelectorAll('[id^=chart-]');
            let drawnCharts = [];
            for (let i = 0; i < resp['jsonObjects'].length; i++) {
                drawnCharts.push(
                    drawChart(charts[i], resp['jsonObjects'][i], resp['titles'][i])
                );
            }
            if (drawnCharts.length !== 0) {
                setChartSize(charts, drawnCharts);
            }            
            spinner.classList.add('d-none');
        })
        .catch(error => {
            console.error('Error loading charts:', error);
            container.innerHTML = '<p class="text-center">Error loading data for charts.</p>'
            spinner.classList.add('d-none');
        });
}


function setChartSize(charts, drawnCharts) {
    const widthSlider = document.getElementById('chartWidthRange');
    const heightSlider = document.getElementById('chartHeightRange');
    widthSlider.min = Math.round(window.screen.width/12);
    widthSlider.max = Math.round(window.screen.width * 0.93);
    heightSlider.min = Math.round(window.screen.height/12);
    heightSlider.max = window.screen.height;
    

    widthSlider.addEventListener("input", (event) => {
        const size = event.target.value;
        charts.forEach(chart => {            
            chart.style.width = size + "px";
            i = chart.id.split('-')[1] - 1;
            drawnCharts[i].resize(opts={width: size});
        });
    });
    heightSlider.addEventListener("input", (event) => {
        const size = event.target.value;
        charts.forEach(chart => {
            chart.style.height = size + "px";
            i = chart.id.split('-')[1] - 1;
            drawnCharts[i].resize(opts={height: size});
        });        
    });
}