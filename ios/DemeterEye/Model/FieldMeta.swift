//
//  FieldMeta.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation

struct FieldMeta: Codable {
    let areaHa: Double?
    let notes: String?
    let crop: String?
    
    // Parameter-based initializer
    init(areaHa: Double? = nil, notes: String? = nil, crop: String? = nil) {
        self.areaHa = areaHa
        self.notes = notes
        self.crop = crop
    }
    
    // Dictionary-based initializer
    init(from dictionary: [String: Any]) throws {
        self.areaHa = dictionary["areaHa"] as? Double
        self.notes = dictionary["notes"] as? String
        self.crop = dictionary["crop"] as? String
    }
}