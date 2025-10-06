//
//  HistoryChartViewModel.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/4/25.
//

import Foundation
import Observation
import CoreGraphics

// MARK: - Metrics

enum HistoryMetric: String, CaseIterable, Hashable, Identifiable {
    case ndvi
    case cloudCover
    case temperatureDegC
    case humidityPct
    
    var id: Self { self }
    
    var displayName: String {
        switch self {
        case .ndvi: return "NDVI"
        case .cloudCover: return "Cloud Cover"
        case .temperatureDegC: return "Temperature"
        case .humidityPct: return "Humidity"
        }
    }
    
    // A hint for default axis domain when shown alone
    var defaultDomain: ClosedRange<Double>? {
        switch self {
        case .ndvi: return 0...1
        case .cloudCover, .humidityPct: return 0...100
        case .temperatureDegC: return nil // varies by field/season
        }
    }
}

// MARK: - Multi-metric point for charting

struct MultiMetricPoint: Identifiable {
    let id = UUID()
    let date: Date
    let metric: HistoryMetric
    let value: Double
    // Optional original record if needed for tooltips
    let original: FieldHistory?
}

@Observable
class HistoryChartViewModel {
    private let history: [FieldHistory]
    private let allChartData: [HistoryDataPoint]
    
    var selectedYear: Int {
        didSet {
            updateFilteredData()
        }
    }
    
    // Which metrics are currently selected to be shown on the chart
    var selectedMetrics: Set<HistoryMetric> = [.ndvi]
    
    // Available years from the data
    let availableYears: [Int]
    
    // Filtered chart data based on selected year
    var chartData: [HistoryDataPoint] = []
    
    init(history: [FieldHistory]) {
        self.history = history
        
        // Parse all data points: include entries that have at least one metric
        self.allChartData = history.compactMap { item in
            guard let date = Self.parseDate(item.date) else { return nil }
            let hasAnyMetric = item.ndvi != nil
                || item.cloudCover != nil
                || item.temperatureDegC != nil
                || item.humidityPct != nil
            guard hasAnyMetric else { return nil }
            return HistoryDataPoint(
                date: date,
                ndvi: item.ndvi,
                cloudCover: item.cloudCover.map { Double($0) },
                temperatureDegC: item.temperatureDegC,
                humidityPct: item.humidityPct,
                originalData: item
            )
        }
        .sorted(by: { $0.date < $1.date })
        
        // Extract available years
        let years = Set(allChartData.map { Calendar.current.component(.year, from: $0.date) })
        self.availableYears = Array(years).sorted(by: >) // Most recent first
        
        // Set default year to most recent
        self.selectedYear = availableYears.first ?? Calendar.current.component(.year, from: Date())
        
        // Initial filter
        updateFilteredData()
    }
    
    // MARK: - Chart sizing and density
    
    // Calculate appropriate chart width based on data points
    func calculateChartWidth(screenWidth: CGFloat) -> CGFloat {
        let dataPointCount = CGFloat(chartData.count)
        
        // For yearly view, use a more reasonable approach
        if dataPointCount > 20 {
            // Show about 15-20 points per screen width for good readability
            let pointsPerScreenWidth: CGFloat = 15
            let totalScreens = max(1, dataPointCount / pointsPerScreenWidth)
            return screenWidth * totalScreens
        } else {
            // For fewer points, ensure minimum width for good visualization
            return max(dataPointCount * 30, screenWidth)
        }
    }
    
    // Determine if points should be shown based on data density
    var shouldShowPoints: Bool {
        // For yearly view, be more generous with showing points since we have fewer
        return chartData.count <= 100
    }
    
    // Get appropriate axis stride based on data density
    var axisStride: Calendar.Component {
        // For yearly view, always use month as it's more appropriate
        return .month
    }
    
    // Shared X-axis domain for the selected year (full year)
    var xAxisDomain: ClosedRange<Date> {
        let cal = Calendar.current
        // Start of selected year
        let start = cal.date(from: DateComponents(year: selectedYear, month: 1, day: 1)) ?? Date(timeIntervalSince1970: 0)
        // End of selected year (23:59:59 on Dec 31)
        let end = cal.date(from: DateComponents(year: selectedYear, month: 12, day: 31, hour: 23, minute: 59, second: 59)) ?? Date()
        return start...end
    }
    
    // MARK: - Filtering
    
    // Filter data for selected year
    private func updateFilteredData() {
        chartData = allChartData.filter { dataPoint in
            Calendar.current.component(.year, from: dataPoint.date) == selectedYear
        }
    }
    
    // Metrics available in the currently selected year (have at least one value)
    var availableMetricsForSelectedYear: Set<HistoryMetric> {
        var set = Set<HistoryMetric>()
        for dp in chartData {
            if dp.ndvi != nil { set.insert(.ndvi) }
            if dp.cloudCover != nil { set.insert(.cloudCover) }
            if dp.temperatureDegC != nil { set.insert(.temperatureDegC) }
            if dp.humidityPct != nil { set.insert(.humidityPct) }
        }
        return set
    }
    
    // Toggle selection, allow empty selection (chart will be empty)
    func toggleMetric(_ metric: HistoryMetric) {
        if selectedMetrics.contains(metric) {
            selectedMetrics.remove(metric)
        } else {
            selectedMetrics.insert(metric)
        }
    }
    
    // Flattened points for all selected metrics in the selected year
    var selectedMultiMetricPoints: [MultiMetricPoint] {
        var points: [MultiMetricPoint] = []
        guard !chartData.isEmpty else { return [] }
        
        for dp in chartData {
            if selectedMetrics.contains(.ndvi), let val = dp.ndvi {
                points.append(MultiMetricPoint(date: dp.date, metric: .ndvi, value: val, original: dp.originalData))
            }
            if selectedMetrics.contains(.cloudCover), let val = dp.cloudCover {
                points.append(MultiMetricPoint(date: dp.date, metric: .cloudCover, value: val, original: dp.originalData))
            }
            if selectedMetrics.contains(.temperatureDegC), let val = dp.temperatureDegC {
                points.append(MultiMetricPoint(date: dp.date, metric: .temperatureDegC, value: val, original: dp.originalData))
            }
            if selectedMetrics.contains(.humidityPct), let val = dp.humidityPct {
                points.append(MultiMetricPoint(date: dp.date, metric: .humidityPct, value: val, original: dp.originalData))
            }
        }
        return points.sorted { $0.date < $1.date }
    }
    
    // Compute a reasonable Y-axis domain across selected metrics
    // If only NDVI is selected, lock to 0...1 for better readability.
    var yAxisDomain: ClosedRange<Double>? {
        // Gather values per selected metric
        var values: [Double] = []
        
        // If only NDVI selected, prefer fixed NDVI domain
        if selectedMetrics == [.ndvi] {
            return HistoryMetric.ndvi.defaultDomain
        }
        
        for dp in chartData {
            if selectedMetrics.contains(.ndvi), let v = dp.ndvi { values.append(v) }
            if selectedMetrics.contains(.cloudCover), let v = dp.cloudCover { values.append(v) }
            if selectedMetrics.contains(.temperatureDegC), let v = dp.temperatureDegC { values.append(v) }
            if selectedMetrics.contains(.humidityPct), let v = dp.humidityPct { values.append(v) }
        }
        
        guard let minV = values.min(), let maxV = values.max() else {
            return nil
        }
        
        // Add a small padding
        let padding = (maxV - minV) * 0.05
        let lower = minV - padding
        let upper = maxV + padding
        
        // Avoid zero span
        if lower == upper {
            return (lower - 1)...(upper + 1)
        }
        return lower...upper
    }
    
    // Get data summary for selected year
    var yearSummary: (dataPoints: Int, dateRange: String) {
        let count = chartData.count
        
        guard let firstDate = chartData.first?.date,
              let lastDate = chartData.last?.date else {
            return (0, "No data")
        }
        
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        
        if Calendar.current.isDate(firstDate, equalTo: lastDate, toGranularity: .day) {
            return (count, formatter.string(from: firstDate))
        } else {
            return (count, "\(formatter.string(from: firstDate)) - \(formatter.string(from: lastDate))")
        }
    }
    
    private static func parseDate(_ dateString: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: dateString)
    }
}

// MARK: - Data container

struct HistoryDataPoint {
    let date: Date
    let ndvi: Double?
    let cloudCover: Double?
    let temperatureDegC: Double?
    let humidityPct: Double?
    let originalData: FieldHistory
}

