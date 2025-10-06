//
//  HistoryDataSummaryView.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/4/25.
//

import SwiftUI

struct HistoryDataSummaryView: View {
    let chartData: [HistoryDataPoint]
    let title: String?
    
    private var header: (count: Int, dateRange: String) {
        let count = chartData.count
        guard let first = chartData.first?.date, let last = chartData.last?.date else {
            return (0, "No data")
        }
        
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        
        if Calendar.current.isDate(first, equalTo: last, toGranularity: .day) {
            return (count, formatter.string(from: first))
        } else {
            return (count, "\(formatter.string(from: first)) - \(formatter.string(from: last))")
        }
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                // Header
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(header.count) entries")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Text(header.dateRange)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal)
                .padding(.top, 8)
                
                // Summary list (most recent first)
                LazyVStack(spacing: 8) {
                    ForEach(chartData.reversed(), id: \.date) { dataPoint in
                        DataSummaryRowView(dataPoint: dataPoint)
                    }
                }
                .padding(.horizontal)
                
                Spacer(minLength: 20)
            }
            .padding(.vertical, 8)
        }
        .background(Color.demeterBackground)
        .navigationTitle(title ?? "Data Summary")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    let sampleHistory = [
        FieldHistory(date: "2025-05-01T00:00:00.000Z", ndvi: 0.78, cloudCover: 20, collection: "sentinel", temperatureDegC: 22.1, humidityPct: 48, cloudcoverPct: 20, windSpeedMps: 2.7, clarityPct: 80),
        FieldHistory(date: "2025-05-18T00:00:00.000Z", ndvi: 0.82, cloudCover: 8, collection: "sentinel", temperatureDegC: 25.3, humidityPct: 45, cloudcoverPct: 8, windSpeedMps: 1.5, clarityPct: 92)
    ]
    // Build the data points like the ViewModel would
    let points: [HistoryDataPoint] = sampleHistory.compactMap { item in
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: item.date) ?? ISO8601DateFormatter().date(from: item.date) else { return nil }
        return HistoryDataPoint(
            date: date,
            ndvi: item.ndvi,
            cloudCover: item.cloudCover.map { Double($0) },
            temperatureDegC: item.temperatureDegC,
            humidityPct: item.humidityPct,
            originalData: item
        )
    }
    return NavigationStack {
        HistoryDataSummaryView(chartData: points, title: "Data Summary - 2025")
    }
}
