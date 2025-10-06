//
//  HistoryChartView.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/4/25.
//

import SwiftUI
import Charts

struct HistoryChartView: View {
    @State private var viewModel: HistoryChartViewModel
    
    init(history: [FieldHistory]) {
        self._viewModel = State(initialValue: HistoryChartViewModel(history: history))
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Year Selector Tabs
                if viewModel.availableYears.count > 1 {
                    YearSelectorSection(
                        availableYears: viewModel.availableYears,
                        selectedYear: viewModel.selectedYear,
                        onSelect: { year in viewModel.selectedYear = year }
                    )
                }
                
                // Metric Selector
                MetricSelectorSection(
                    availableMetrics: viewModel.availableMetricsForSelectedYear,
                    selectedMetrics: viewModel.selectedMetrics,
                    onToggle: { metric in viewModel.toggleMetric(metric) }
                )
                
                // Chart Section: small multiples (one chart per metric) with per-metric scales
                ChartSectionView(
                    title: "Field Metrics Over Time - \(viewModel.selectedYear)",
                    datesCount: viewModel.chartData.count,
                    dateRangeText: viewModel.yearSummary.dateRange,
                    points: viewModel.selectedMultiMetricPoints,
                    selectedMetrics: viewModel.selectedMetrics,
                    yAxisDomain: viewModel.yAxisDomain, // not used in small multiples but kept for compatibility
                    axisStride: viewModel.axisStride,
                    shouldShowPoints: viewModel.shouldShowPoints,
                    chartWidth: calculateChartWidth(),
                    xAxisDomain: viewModel.xAxisDomain
                )
                
                // Data Summary Navigation
                NavigationLink {
                    HistoryDataSummaryView(
                        chartData: viewModel.chartData,
                        title: "Data Summary - \(viewModel.selectedYear)"
                    )
                } label: {
                    SummaryNavigationCardView(
                        title: "Data Summary",
                        subtitle: viewModel.yearSummary.dateRange,
                        countText: "\(viewModel.yearSummary.dataPoints) entries",
                        icon: "list.bullet.rectangle",
                        iconColor: .demeterGreen
                    )
                }
                .buttonStyle(PlainButtonStyle())
                .padding(.horizontal)
                
                Spacer(minLength: 20)
            }
        }
        .background(Color.demeterBackground)
        .navigationTitle("Field History")
        .navigationBarTitleDisplayMode(.large)
    }
    
    private func calculateChartWidth() -> CGFloat {
        let screenWidth = UIScreen.main.bounds.width - 32
        return viewModel.calculateChartWidth(screenWidth: screenWidth)
    }
}

// MARK: - Sections

private struct YearSelectorSection: View {
    let availableYears: [Int]
    let selectedYear: Int
    let onSelect: (Int) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Select Year")
                .font(.headline)
                .fontWeight(.semibold)
                .padding(.horizontal)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(availableYears, id: \.self) { year in
                        YearTabView(
                            year: String(year),
                            isSelected: year == selectedYear,
                            action: { onSelect(year) }
                        )
                    }
                }
                .padding(.horizontal)
            }
        }
    }
}

private struct MetricSelectorSection: View {
    let availableMetrics: Set<HistoryMetric>
    let selectedMetrics: Set<HistoryMetric>
    let onToggle: (HistoryMetric) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Select Metrics")
                .font(.headline)
                .fontWeight(.semibold)
                .padding(.horizontal)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(HistoryMetric.allCases) { metric in
                        let isAvailable = availableMetrics.contains(metric)
                        MetricChip(
                            title: metric.displayName,
                            color: color(for: metric),
                            isSelected: selectedMetrics.contains(metric),
                            isEnabled: isAvailable,
                            action: { onToggle(metric) }
                        )
                        .opacity(isAvailable ? 1.0 : 0.4)
                    }
                }
                .padding(.horizontal)
            }
        }
    }
    
    // Color mapping for metrics
    private func color(for metric: HistoryMetric) -> Color {
        switch metric {
        case .ndvi: return .demeterGreen
        case .cloudCover: return .blue
        case .temperatureDegC: return .red
        case .humidityPct: return .teal
        }
    }
}

private struct ChartSectionView: View {
    let title: String
    let datesCount: Int
    let dateRangeText: String
    let points: [MultiMetricPoint]
    let selectedMetrics: Set<HistoryMetric>
    let yAxisDomain: ClosedRange<Double>?
    let axisStride: Calendar.Component
    let shouldShowPoints: Bool
    let chartWidth: CGFloat
    let xAxisDomain: ClosedRange<Date>
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(datesCount) dates")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text(dateRangeText)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal)
            
            let orderedMetrics: [HistoryMetric] = HistoryMetric
                .allCases
                .filter { selectedMetrics.contains($0) }
            
            if orderedMetrics.isEmpty {
                Text("Select metrics to display")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.horizontal)
                    .padding(.top, 8)
            } else {
                ScrollView(.horizontal, showsIndicators: true) {
                    VStack(alignment: .leading, spacing: 16) {
                        ForEach(orderedMetrics, id: \.self) { metric in
                            let metricPoints = points.filter { $0.metric == metric }
                            
                            // Header per metric
                            HStack(spacing: 8) {
                                Circle()
                                    .fill(color(for: metric))
                                    .frame(width: 10, height: 10)
                                Text(metric.displayName)
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.primary)
                            }
                            .padding(.horizontal)
                            
                            // Compute per-metric domain once
                            let domain = perMetricDomain(for: metric, points: metricPoints)
                            let baseColor = color(for: metric)
                            let hasData = !metricPoints.isEmpty
                            
                            Chart(metricPoints) { (point: MultiMetricPoint) in
                                let status = (point.original?.type == 1) ? "Forecast" : "Actual"
                                
                                LineMark(
                                    x: .value("Date", point.date),
                                    y: .value("Value", point.value)
                                )
                                .foregroundStyle(by: .value("Status", status))
                                .lineStyle(StrokeStyle(lineWidth: 2))
                                
                                if shouldShowPoints {
                                    PointMark(
                                        x: .value("Date", point.date),
                                        y: .value("Value", point.value)
                                    )
                                    .foregroundStyle(by: .value("Status", status))
                                    .symbol(.circle)
                                    .symbolSize(30)
                                }
                                
                                // When no data, add invisible marks at domain bounds
                                // to ensure axes render even with empty datasets.
                                if !hasData {
                                    RuleMark(x: .value("Date", xAxisDomain.lowerBound))
                                        .opacity(0)
                                    RuleMark(x: .value("Date", xAxisDomain.upperBound))
                                        .opacity(0)
                                }
                            }
                            // Map both series ("Actual"/"Forecast") to the same color with different opacity
                            .chartForegroundStyleScale(
                                domain: ["Actual", "Forecast"],
                                range: [baseColor, baseColor.opacity(0.35)]
                            )
                            .chartXAxis {
                                AxisMarks(values: .stride(by: axisStride)) { value in
                                    AxisValueLabel {
                                        if let date = value.as(Date.self) {
                                            Text(date.formatted(.dateTime.month(.abbreviated).year(.twoDigits)))
                                        }
                                    }
                                    AxisGridLine()
                                    AxisTick()
                                }
                            }
                            .chartYAxis {
                                AxisMarks { value in
                                    AxisValueLabel {
                                        if let y = value.as(Double.self) {
                                            Text(yAxisLabel(for: y, metric: metric, domain: domain))
                                        }
                                    }
                                    AxisGridLine()
                                    AxisTick()
                                }
                            }
                            .chartYAxisScale(optionalDomain: domain)
                            .chartXScale(domain: xAxisDomain)
                            .frame(width: chartWidth, height: 240)
                            .padding(.horizontal)
                            .chartLegend(.hidden)
                        }
                    }
                }
            }
        }
    }
    
    // Color mapping for metrics
    private func color(for metric: HistoryMetric) -> Color {
        switch metric {
        case .ndvi: return .demeterGreen
        case .cloudCover: return .blue
        case .temperatureDegC: return .red
        case .humidityPct: return .teal
        }
    }
    
    // Compute per-metric Y-axis domain with sensible defaults and padding
    private func perMetricDomain(for metric: HistoryMetric, points: [MultiMetricPoint]) -> ClosedRange<Double>? {
        // If we have no points, return default if any
        guard !points.isEmpty else {
            return metric.defaultDomain
        }
        
        let values = points.map { $0.value }
        guard let minV = values.min(), let maxV = values.max() else {
            return metric.defaultDomain
        }
        
        // 5% padding
        let span = max(0.0001, maxV - minV)
        let padding = span * 0.05
        
        switch metric {
        case .ndvi:
            // Keep NDVI locked to 0...1 for comparability
            return 0...1
        case .cloudCover, .humidityPct:
            // Clamp to 0...100 with padding inside bounds
            let lower = max(0, minV - padding)
            let upper = min(100, maxV + padding)
            if lower == upper {
                return max(0, lower - 1)...min(100, upper + 1)
            }
            return lower...upper
        case .temperatureDegC:
            let lower = minV - padding
            let upper = maxV + padding
            if lower == upper {
                return (lower - 1)...(upper + 1)
            }
            return lower...upper
        }
    }
    
    // Y-axis label formatting per metric
    private func yAxisLabel(for value: Double, metric: HistoryMetric, domain: ClosedRange<Double>?) -> String {
        switch metric {
        case .ndvi:
            return String(format: "%.2f", value)
        case .cloudCover, .humidityPct:
            return String(format: "%.0f%%", value)
        case .temperatureDegC:
            // If range is wide, show whole degrees; otherwise tenths
            if let d = domain, (d.upperBound - d.lowerBound) > 10 {
                return String(format: "%.0f°", value)
            } else {
                return String(format: "%.1f°", value)
            }
        }
    }
}

// Conditional Y-axis scale as a ViewModifier to avoid opaque return mismatches
private struct OptionalYAxisScaleModifier: ViewModifier {
    let domain: ClosedRange<Double>?
    func body(content: Content) -> some View {
        if let domain {
            content.chartYScale(domain: domain)
        } else {
            content.chartYScale()
        }
    }
}

private extension View {
    func chartYAxisScale(optionalDomain: ClosedRange<Double>?) -> some View {
        modifier(OptionalYAxisScaleModifier(domain: optionalDomain))
    }
}

struct DataSummaryRowView: View {
    let dataPoint: HistoryDataPoint
    
    private var ndviText: String {
        if let ndvi = dataPoint.ndvi {
            return String(format: "NDVI: %.3f", ndvi)
        } else {
            return "NDVI: —"
        }
    }
    
    private var temperatureText: String {
        if let temp = dataPoint.temperatureDegC {
            return String(format: "Temp: %.1f°C", temp)
        } else {
            return "Temp: —"
        }
    }
    
    private var humidityText: String {
        if let humidity = dataPoint.humidityPct {
            return String(format: "Humidity: %.0f%%", humidity)
        } else {
            return "Humidity: —"
        }
    }
    
    private var cloudCoverText: String {
        if let cc = dataPoint.cloudCover {
            return String(format: "Clouds: %.0f%%", cc)
        } else {
            return "Clouds: —"
        }
    }
    
    private var clarityText: String {
        if let clarity = dataPoint.originalData.clarityPct {
            return String(format: "Clarity: %.0f%%", clarity)
        } else {
            return "Clarity: —"
        }
    }
    
    var body: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(dataPoint.date.formatted(date: .abbreviated, time: .omitted))
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(ndviText)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text(temperatureText)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text(humidityText)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text(cloudCoverText)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text(clarityText)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color.gray.opacity(0.05))
        .cornerRadius(8)
    }
}

struct YearTabView: View {
    let year: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Text("\(year)")
                    .font(.subheadline)
                    .fontWeight(isSelected ? .semibold : .medium)
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.caption)
                }
            }
            .foregroundColor(isSelected ? .white : .demeterGreen)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(isSelected ? Color.demeterGreen : Color.demeterGreen.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20)
                    .stroke(Color.demeterGreen, lineWidth: isSelected ? 0 : 1)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct MetricChip: View {
    let title: String
    let color: Color
    let isSelected: Bool
    let isEnabled: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: {
            if isEnabled { action() }
        }) {
            Text(title)
                .font(.subheadline)
                .fontWeight(isSelected ? .semibold : .medium)
                .foregroundColor(isSelected ? .white : color)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 20)
                        .fill(isSelected ? color : color.opacity(0.1))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(color, lineWidth: isSelected ? 0 : 1)
                )
        }
        .buttonStyle(.plain)
        .disabled(!isEnabled)
    }
}

// A small card-style navigation button consistent with the app's design
struct SummaryNavigationCardView: View {
    let title: String
    let subtitle: String
    let countText: String
    let icon: String
    let iconColor: Color
    
    var body: some View {
        HStack(spacing: 16) {
            Circle()
                .fill(iconColor.opacity(0.1))
                .frame(width: 50, height: 50)
                .overlay(
                    Image(systemName: icon)
                        .foregroundColor(iconColor)
                        .font(.title2)
                )
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                
                Text(countText)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
            
            Spacer()
            
            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
                .font(.subheadline)
        }
        .padding(20)
        .background(Color.white)
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.05), radius: 8, x: 0, y: 2)
    }
}

#Preview {
    let sampleHistory = [
        // 2023 data
        FieldHistory(date: "2023-03-15T00:00:00.000Z", ndvi: 0.20, cloudCover: 12, collection: "sentinel", temperatureDegC: 7.2, humidityPct: 68, cloudcoverPct: 12, windSpeedMps: 2.1, clarityPct: 88),
        FieldHistory(date: "2023-06-01T00:00:00.000Z", ndvi: 0.75, cloudCover: 8, collection: "sentinel", temperatureDegC: 21.5, humidityPct: 52, cloudcoverPct: 8, windSpeedMps: 1.9, clarityPct: 92),
        FieldHistory(date: "2023-09-15T00:00:00.000Z", ndvi: 0.45, cloudCover: 15, collection: "sentinel", temperatureDegC: 16.8, humidityPct: 62, cloudcoverPct: 15, windSpeedMps: 2.8, clarityPct: 85),
        
        // 2024 data
        FieldHistory(date: "2024-03-15T00:00:00.000Z", ndvi: 0.25, cloudCover: 10, collection: "sentinel", temperatureDegC: 8.5, humidityPct: 65, cloudcoverPct: 10, windSpeedMps: 2.3, clarityPct: 90),
        FieldHistory(date: "2024-04-01T00:00:00.000Z", ndvi: 0.45, cloudCover: 15, collection: "sentinel", temperatureDegC: 12.8, humidityPct: 58, cloudcoverPct: 15, windSpeedMps: 3.1, clarityPct: 85),
        FieldHistory(date: "2024-04-15T00:00:00.000Z", ndvi: 0.62, cloudCover: 5, collection: "sentinel", temperatureDegC: 18.2, humidityPct: 52, cloudcoverPct: 5, windSpeedMps: 1.8, clarityPct: 95),
        
        // 2025 data
        FieldHistory(date: "2025-05-01T00:00:00.000Z", ndvi: 0.78, cloudCover: 20, collection: "sentinel", temperatureDegC: 22.1, humidityPct: 48, cloudcoverPct: 20, windSpeedMps: 2.7, clarityPct: 80, type: 1),
        FieldHistory(date: "2025-05-18T00:00:00.000Z", ndvi: 0.82, cloudCover: 8, collection: "sentinel", temperatureDegC: 25.3, humidityPct: 45, cloudcoverPct: 8, windSpeedMps: 1.5, clarityPct: 92, type: 1)
    ]
    
    HistoryChartView(history: sampleHistory)
}

