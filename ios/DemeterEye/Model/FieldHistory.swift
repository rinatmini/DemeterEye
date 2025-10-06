//
//  FieldHistory.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation

struct FieldHistory: Codable {
    let date: String
    let ndvi: Double?
    let cloudCover: Int?
    let collection: String?
    let temperatureDegC: Double?
    let humidityPct: Double?
    let cloudcoverPct: Double?
    let windSpeedMps: Double?
    let clarityPct: Double?
    let type: Int?
    
    enum CodingKeys: String, CodingKey {
        case date, ndvi, collection
        case cloudCover = "cloud_cover"
        case temperatureDegC = "temperature_deg_c"
        case humidityPct = "humidity_pct"
        case cloudcoverPct = "cloudcover_pct"
        case windSpeedMps = "wind_speed_mps"
        case clarityPct = "clarity_pct"
        case type
    }
    
    // Parameter-based initializer
    init(
        date: String,
        ndvi: Double? = nil,
        cloudCover: Int? = nil,
        collection: String? = nil,
        temperatureDegC: Double? = nil,
        humidityPct: Double? = nil,
        cloudcoverPct: Double? = nil,
        windSpeedMps: Double? = nil,
        clarityPct: Double? = nil,
        type: Int? = nil
    ) {
        self.date = date
        self.ndvi = ndvi
        self.cloudCover = cloudCover
        self.collection = collection
        self.temperatureDegC = temperatureDegC
        self.humidityPct = humidityPct
        self.cloudcoverPct = cloudcoverPct
        self.windSpeedMps = windSpeedMps
        self.clarityPct = clarityPct
        self.type = type
    }
    
    // Dictionary-based initializer
    init(from dictionary: [String: Any]) throws {
        guard let date = dictionary["date"] as? String else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Missing required field 'date' in FieldHistory dictionary")
            )
        }
        
        self.date = date
        self.ndvi = dictionary["ndvi"] as? Double
        self.cloudCover = dictionary["cloud_cover"] as? Int
        self.collection = dictionary["collection"] as? String
        self.temperatureDegC = dictionary["temperature_deg_c"] as? Double
        self.humidityPct = dictionary["humidity_pct"] as? Double
        self.cloudcoverPct = dictionary["cloudcover_pct"] as? Double
        self.windSpeedMps = dictionary["wind_speed_mps"] as? Double
        self.clarityPct = dictionary["clarity_pct"] as? Double
        self.type = dictionary["type"] as? Int
    }
}
