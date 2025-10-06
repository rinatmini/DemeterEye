//
//  DateExtensions.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation

extension Date {
    var dayOfYear: Int {
        Calendar.current.ordinality(of: .day, in: .year, for: self) ?? 0
    }
}

extension String {
    func toDate() -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: self)
    }
    
    func formatAsDisplayDate() -> String {
        guard let date = self.toDate() else { return self }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        return displayFormatter.string(from: date)
    }
}