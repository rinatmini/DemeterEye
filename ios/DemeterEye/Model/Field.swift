//
//  Field.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation
import CoreLocation

struct Field: Codable, Identifiable {
    let id: String
    let ownerId: String
    let name: String
    let geometry: GeoJSONGeometry
    let createdAt: String
    let meta: FieldMeta
    let history: [FieldHistory]?
    let forecast: ForecastData?
    
    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case ownerId, name, geometry, createdAt, meta, history, forecast
    }
    
    // Parameter-based initializer
    init(
        id: String,
        ownerId: String,
        name: String,
        geometry: GeoJSONGeometry,
        createdAt: String,
        meta: FieldMeta,
        history: [FieldHistory]? = nil,
        forecast: ForecastData? = nil
    ) {
        self.id = id
        self.ownerId = ownerId
        self.name = name
        self.geometry = geometry
        self.createdAt = createdAt
        self.meta = meta
        self.history = history
        self.forecast = forecast
    }
    
    // Dictionary-based initializer
    init(from dictionary: [String: Any]) throws {
        guard let id = dictionary["_id"] as? String ?? dictionary["id"] as? String,
              let ownerId = dictionary["ownerId"] as? String,
              let name = dictionary["name"] as? String,
              let geometryDict = dictionary["geometry"] as? [String: Any],
              let createdAt = dictionary["createdAt"] as? String,
              let metaDict = dictionary["meta"] as? [String: Any] else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Missing required fields in Field dictionary")
            )
        }
        
        self.id = id
        self.ownerId = ownerId
        self.name = name
        
        // Parse geometry from dictionary to GeoJSONGeometry
        let geometryData = try JSONSerialization.data(withJSONObject: geometryDict)
        self.geometry = try JSONDecoder().decode(GeoJSONGeometry.self, from: geometryData)
        
        self.createdAt = createdAt
        self.meta = try FieldMeta(from: metaDict)
        
        // Optional fields
        if let historyArray = dictionary["history"] as? [[String: Any]] {
            self.history = try historyArray.map { try FieldHistory(from: $0) }
        } else {
            self.history = nil
        }
        
        if let forecastDict = dictionary["forecast"] as? [String: Any] {
            self.forecast = try ForecastData(from: forecastDict)
        } else {
            self.forecast = nil
        }
    }
    
    // Computed properties for easy access
    var cropType: String {
        meta.crop?.capitalized ?? "Unknown"
    }
    
    var areaText: String {
        guard let area = meta.areaHa else { return "Unknown area" }
        return String(format: "%.1f ha", area)
    }
    
    var coordinates: [CLLocationCoordinate2D] {
        return geometry.allCoordinates
    }
    
    var centerCoordinate: CLLocationCoordinate2D {
        return geometry.centerCoordinate
    }
    
    // MARK: - Geometry Convenience Methods
    
    /// Get polygon coordinates if this field is a polygon
    var polygonCoordinates: [CLLocationCoordinate2D]? {
        guard case .polygon(let polygon) = geometry else { return nil }
        return polygon.outerRingCoordinates
    }
    
    /// Check if the field geometry contains a given coordinate
    func contains(coordinate: CLLocationCoordinate2D) -> Bool {
        guard case .polygon(let polygon) = geometry else { return false }
        
        let ring = polygon.outerRingCoordinates
        guard ring.count >= 3 else { return false }
        
        var inside = false
        var j = ring.count - 1
        
        for i in 0..<ring.count {
            let xi = ring[i].longitude
            let yi = ring[i].latitude
            let xj = ring[j].longitude
            let yj = ring[j].latitude
            
            if ((yi > coordinate.latitude) != (yj > coordinate.latitude)) &&
                (coordinate.longitude < (xj - xi) * (coordinate.latitude - yi) / (yj - yi) + xi) {
                inside.toggle()
            }
            j = i
        }
        
        return inside
    }
}



// MARK: - Field Convenience Extensions

extension Field {
    /// Create a field with a simple polygon from coordinate pairs
    static func withPolygon(
        id: String,
        ownerId: String,
        name: String,
        coordinates: [(longitude: Double, latitude: Double)],
        createdAt: String,
        meta: FieldMeta,
        history: [FieldHistory]? = nil,
        forecast: ForecastData? = nil
    ) -> Field {
        let positions = coordinates.map { Position(longitude: $0.longitude, latitude: $0.latitude) }
        let polygon = Polygon(coordinates: [positions])
        let geometry = GeoJSONGeometry.polygon(polygon)
        
        return Field(
            id: id,
            ownerId: ownerId,
            name: name,
            geometry: geometry,
            createdAt: createdAt,
            meta: meta,
            history: history,
            forecast: forecast
        )
    }
    
    /// Create a simple rectangular field
    static func withRectangle(
        id: String,
        ownerId: String,
        name: String,
        center: CLLocationCoordinate2D,
        widthMeters: Double,
        heightMeters: Double,
        createdAt: String,
        meta: FieldMeta,
        history: [FieldHistory]? = nil,
        forecast: ForecastData? = nil
    ) -> Field {
        // Approximate conversion from meters to degrees (this is simplified)
        let latDelta = heightMeters / 111111.0 // ~111km per degree latitude
        let lonDelta = widthMeters / (111111.0 * cos(center.latitude * .pi / 180)) // Adjusted for longitude
        
        let positions = [
            Position(longitude: center.longitude - lonDelta/2, latitude: center.latitude - latDelta/2),
            Position(longitude: center.longitude + lonDelta/2, latitude: center.latitude - latDelta/2),
            Position(longitude: center.longitude + lonDelta/2, latitude: center.latitude + latDelta/2),
            Position(longitude: center.longitude - lonDelta/2, latitude: center.latitude + latDelta/2),
            Position(longitude: center.longitude - lonDelta/2, latitude: center.latitude - latDelta/2) // Close the ring
        ]
        
        let polygon = Polygon(coordinates: [positions])
        let geometry = GeoJSONGeometry.polygon(polygon)
        
        return Field(
            id: id,
            ownerId: ownerId,
            name: name,
            geometry: geometry,
            createdAt: createdAt,
            meta: meta,
            history: history,
            forecast: forecast
        )
    }
    
    /// Update the field's geometry
    func withGeometry(_ newGeometry: GeoJSONGeometry) -> Field {
        return Field(
            id: self.id,
            ownerId: self.ownerId,
            name: self.name,
            geometry: newGeometry,
            createdAt: self.createdAt,
            meta: self.meta,
            history: self.history,
            forecast: self.forecast
        )
    }
    
    /// Get the area in hectares (approximation for polygons)
    var approximateAreaHectares: Double {
        guard case .polygon(let polygon) = geometry else {
            return meta.areaHa ?? 0.0 // Fallback to metadata value or 0 if nil
        }
        
        // Simple polygon area calculation (Shoelace formula)
        let coords = polygon.outerRingCoordinates
        guard coords.count >= 3 else { return 0.0 }
        
        var area = 0.0
        for i in 0..<coords.count {
            let j = (i + 1) % coords.count
            area += coords[i].longitude * coords[j].latitude
            area -= coords[j].longitude * coords[i].latitude
        }
        area = abs(area) / 2.0
        
        // Convert from square degrees to hectares (very rough approximation)
        // This is highly simplified and should be replaced with proper geospatial calculations
        let hectares = area * 12100.0 // Approximate conversion factor
        
        return hectares
    }
}

