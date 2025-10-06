//
//  ForecastData.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation

struct ForecastData: Codable {
    let year: Int
    let yieldTph: Double?
    let ndviPeak: Double?
    let ndviPeakAt: String?
    
    // New fields based on updated backend format
    let yieldModel: String?
    let yieldConfidence: Double?
    let ndviStartAt: String?
    let ndviEndAt: String?
    let ndviModel: String?
    let ndviConfidence: Double?
    
    // Kept for backward compatibility with existing code usage
    // These are derived from the new fields when possible.
    @available(*, deprecated, message: "Use yieldModel or ndviModel instead.")
    var model: String? { yieldModel ?? ndviModel }
    
    @available(*, deprecated, message: "Use yieldConfidence or ndviConfidence instead.")
    var confidence: Double? { yieldConfidence ?? ndviConfidence }
    
    // Kept to avoid breaking builds if referenced elsewhere; may be nil as backend may not provide it anymore.
    let updatedAt: String?
    
    // Parameter-based initializer
    init(
        year: Int,
        yieldTph: Double? = nil,
        ndviPeak: Double? = nil,
        ndviPeakAt: String? = nil,
        yieldModel: String? = nil,
        yieldConfidence: Double? = nil,
        ndviStartAt: String? = nil,
        ndviEndAt: String? = nil,
        ndviModel: String? = nil,
        ndviConfidence: Double? = nil,
        updatedAt: String? = nil
    ) {
        self.year = year
        self.yieldTph = yieldTph
        self.ndviPeak = ndviPeak
        self.ndviPeakAt = ndviPeakAt
        self.yieldModel = yieldModel
        self.yieldConfidence = yieldConfidence
        self.ndviStartAt = ndviStartAt
        self.ndviEndAt = ndviEndAt
        self.ndviModel = ndviModel
        self.ndviConfidence = ndviConfidence
        self.updatedAt = updatedAt
    }
    
    // Dictionary-based initializer (supports both new and legacy keys)
    init(from dictionary: [String: Any]) throws {
        guard let year = dictionary["year"] as? Int else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Missing required 'year' field in ForecastData dictionary")
            )
        }
        self.year = year
        
        self.yieldTph = ForecastData.double(from: dictionary["yieldTph"])
        self.ndviPeak = ForecastData.double(from: dictionary["ndviPeak"])
        self.ndviPeakAt = dictionary["ndviPeakAt"] as? String
        
        // Prefer new keys, fall back to legacy where applicable
        self.yieldModel = (dictionary["yieldModel"] as? String) ?? (dictionary["model"] as? String)
        self.yieldConfidence = ForecastData.double(from: dictionary["yieldConfidence"]) ?? ForecastData.double(from: dictionary["confidence"])
        
        self.ndviStartAt = dictionary["ndviStartAt"] as? String
        self.ndviEndAt = dictionary["ndviEndAt"] as? String
        self.ndviModel = dictionary["ndviModel"] as? String
        self.ndviConfidence = ForecastData.double(from: dictionary["ndviConfidence"])
        
        self.updatedAt = dictionary["updatedAt"] as? String
    }
    
    // Custom CodingKeys to support both new and legacy keys
    private enum CodingKeys: String, CodingKey {
        case year
        case yieldTph
        case ndviPeak
        case ndviPeakAt
        case yieldModel
        case yieldConfidence
        case ndviStartAt
        case ndviEndAt
        case ndviModel
        case ndviConfidence
        case updatedAt
        
        // Legacy keys for backward compatibility (decode-only)
        case model
        case confidence
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        self.year = try container.decode(Int.self, forKey: .year)
        self.yieldTph = try container.decodeIfPresent(Double.self, forKey: .yieldTph)
        self.ndviPeak = try container.decodeIfPresent(Double.self, forKey: .ndviPeak)
        self.ndviPeakAt = try container.decodeIfPresent(String.self, forKey: .ndviPeakAt)
        
        // Prefer new keys; fall back to legacy where reasonable
        self.yieldModel = try container.decodeIfPresent(String.self, forKey: .yieldModel)
            ?? container.decodeIfPresent(String.self, forKey: .model)
        
        self.yieldConfidence = try container.decodeIfPresent(Double.self, forKey: .yieldConfidence)
            ?? container.decodeIfPresent(Double.self, forKey: .confidence)
        
        self.ndviStartAt = try container.decodeIfPresent(String.self, forKey: .ndviStartAt)
        self.ndviEndAt = try container.decodeIfPresent(String.self, forKey: .ndviEndAt)
        self.ndviModel = try container.decodeIfPresent(String.self, forKey: .ndviModel)
        self.ndviConfidence = try container.decodeIfPresent(Double.self, forKey: .ndviConfidence)
        
        self.updatedAt = try container.decodeIfPresent(String.self, forKey: .updatedAt)
    }
    
    // Custom Encodable implementation to avoid encoding legacy keys
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(year, forKey: .year)
        try container.encodeIfPresent(yieldTph, forKey: .yieldTph)
        try container.encodeIfPresent(ndviPeak, forKey: .ndviPeak)
        try container.encodeIfPresent(ndviPeakAt, forKey: .ndviPeakAt)
        try container.encodeIfPresent(yieldModel, forKey: .yieldModel)
        try container.encodeIfPresent(yieldConfidence, forKey: .yieldConfidence)
        try container.encodeIfPresent(ndviStartAt, forKey: .ndviStartAt)
        try container.encodeIfPresent(ndviEndAt, forKey: .ndviEndAt)
        try container.encodeIfPresent(ndviModel, forKey: .ndviModel)
        try container.encodeIfPresent(ndviConfidence, forKey: .ndviConfidence)
        try container.encodeIfPresent(updatedAt, forKey: .updatedAt)
        
        // If you need to support older consumers, you could also encode legacy keys:
        // try container.encodeIfPresent(yieldModel ?? ndviModel, forKey: .model)
        // try container.encodeIfPresent(yieldConfidence ?? ndviConfidence, forKey: .confidence)
    }
    
    // Helper to robustly parse doubles from heterogeneous [String: Any] sources
    private static func double(from any: Any?) -> Double? {
        if let d = any as? Double { return d }
        if let i = any as? Int { return Double(i) }
        if let n = any as? NSNumber { return n.doubleValue }
        if let s = any as? String, let d = Double(s) { return d }
        return nil
    }
}
