//
//  ModernFieldExamples.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation
import CoreLocation

/// Examples demonstrating the modernized Field struct with direct GeoJSON support
struct ModernFieldExamples {
    
    // MARK: - Creating Fields with Different Geometry Types
    
    /// Create a field with a polygon boundary (most common case)
    static func createPolygonField() -> Field {
        // Create supporting data
        let meta = FieldMeta(areaHa: 25.5, notes: "Prime agricultural land with good drainage", crop: "corn")
        let forecast = ForecastData(year: 2025, yieldTph: 12.5, ndviPeak: 0.88, ndviPeakAt: "2025-07-20", yieldModel: "RandomForest", yieldConfidence: 0.94, updatedAt: "2025-10-02T08:00:00Z")
        
        // Create polygon geometry with outer ring and a hole
        let outerRing = [
            Position(longitude: -95.5, latitude: 40.0),
            Position(longitude: -95.4, latitude: 40.0),
            Position(longitude: -95.4, latitude: 40.1),
            Position(longitude: -95.5, latitude: 40.1),
            Position(longitude: -95.5, latitude: 40.0) // Close the ring
        ]
        
        let hole = [
            Position(longitude: -95.47, latitude: 40.02),
            Position(longitude: -95.43, latitude: 40.02),
            Position(longitude: -95.43, latitude: 40.08),
            Position(longitude: -95.47, latitude: 40.08),
            Position(longitude: -95.47, latitude: 40.02) // Close the hole
        ]
        
        let polygon = Polygon(coordinates: [outerRing, hole])
        let geometry = GeoJSONGeometry.polygon(polygon)
        
        return Field(
            id: "corn-field-001",
            ownerId: "farmer-123",
            name: "North Corn Field",
            geometry: geometry,
            createdAt: "2025-01-15T10:00:00Z",
            meta: meta,
            history: [],
            forecast: forecast
        )
    }
    
    /// Create a field using the convenience polygon method
    static func createSimplePolygonField() -> Field {
        let meta = FieldMeta(areaHa: 15.2, notes: "Wheat field with excellent soil", crop: "wheat")
        let forecast = ForecastData(year: 2025, yieldTph: 8.2, ndviPeak: 0.83, ndviPeakAt: "2025-06-28", yieldModel: "SVM", yieldConfidence: 0.89, updatedAt: "2025-10-02T08:00:00Z")
        
        return Field.withPolygon(
            id: "wheat-field-002",
            ownerId: "farmer-123",
            name: "East Wheat Field",
            coordinates: [
                (longitude: -95.3, latitude: 40.1),
                (longitude: -95.2, latitude: 40.1),
                (longitude: -95.2, latitude: 40.2),
                (longitude: -95.3, latitude: 40.2),
                (longitude: -95.3, latitude: 40.1)
            ],
            createdAt: "2025-02-01T14:30:00Z",
            meta: meta,
            forecast: forecast
        )
    }
    
    /// Create a rectangular field using the convenience method
    static func createRectangularField() -> Field {
        let meta = FieldMeta(areaHa: 50.0, notes: "Large rectangular soybean field", crop: "soybean")
        let forecast = ForecastData(year: 2025, yieldTph: 3.2, ndviPeak: 0.86, ndviPeakAt: "2025-07-29", yieldModel: "NeuralNet", yieldConfidence: 0.91, updatedAt: "2025-10-02T08:00:00Z")
        
        let center = CLLocationCoordinate2D(latitude: 40.0, longitude: -95.5)
        
        return Field.withRectangle(
            id: "soybean-field-003",
            ownerId: "farmer-456",
            name: "Rectangular Soybean Field",
            center: center,
            widthMeters: 1000, // 1km wide
            heightMeters: 500,  // 0.5km tall
            createdAt: "2025-03-01T09:00:00Z",
            meta: meta,
            forecast: forecast
        )
    }
    
    /// Create a field with point geometry (for small plots or specific locations)
    static func createPointField() -> Field {
        let meta = FieldMeta(areaHa: 0.1, notes: "Research plot", crop: "experimental")
        let forecast = ForecastData(year: 2025, yieldTph: 5.0, ndviPeak: 0.80, ndviPeakAt: "2025-07-10", yieldModel: "Experimental", yieldConfidence: 0.75, updatedAt: "2025-10-02T08:00:00Z")
        
        let point = Point(longitude: -95.1, latitude: 40.05)
        let geometry = GeoJSONGeometry.point(point)
        
        return Field(
            id: "research-plot-001",
            ownerId: "research-team",
            name: "Research Plot Alpha",
            geometry: geometry,
            createdAt: "2025-04-01T12:00:00Z",
            meta: meta,
            history: [],
            forecast: forecast
        )
    }
    
    /// Create a field with multi-polygon geometry (farm with disconnected plots)
    static func createMultiPolygonField() -> Field {
        let meta = FieldMeta(areaHa: 35.0, notes: "Two separate field plots", crop: "rice")
        let forecast = ForecastData(year: 2025, yieldTph: 7.8, ndviPeak: 0.90, ndviPeakAt: "2025-08-08", yieldModel: "Ensemble", yieldConfidence: 0.87, updatedAt: "2025-10-02T08:00:00Z")
        
        // First field polygon
        let field1 = [
            [
                Position(longitude: -95.5, latitude: 40.0),
                Position(longitude: -95.4, latitude: 40.0),
                Position(longitude: -95.4, latitude: 40.1),
                Position(longitude: -95.5, latitude: 40.1),
                Position(longitude: -95.5, latitude: 40.0)
            ]
        ]
        
        // Second field polygon (disconnected)
        let field2 = [
            [
                Position(longitude: -95.2, latitude: 40.2),
                Position(longitude: -95.1, latitude: 40.2),
                Position(longitude: -95.1, latitude: 40.3),
                Position(longitude: -95.2, latitude: 40.3),
                Position(longitude: -95.2, latitude: 40.2)
            ]
        ]
        
        let multiPolygon = MultiPolygon(coordinates: [field1, field2])
        let geometry = GeoJSONGeometry.multiPolygon(multiPolygon)
        
        return Field(
            id: "rice-multi-field-004",
            ownerId: "farmer-789",
            name: "Twin Rice Fields",
            geometry: geometry,
            createdAt: "2025-04-15T11:00:00Z",
            meta: meta,
            history: [],
            forecast: forecast
        )
    }
    
    // MARK: - Working with Field Geometries
    
    /// Demonstrate geometry analysis and operations
    static func analyzeFieldGeometry() {
        let field = createPolygonField()
        
        print("=== Field Geometry Analysis ===")
        print("Field: \(field.name)")
        print("Crop: \(field.cropType)")
        print("Area: \(field.areaText)")
        
        // Basic coordinate information
        let allCoords = field.coordinates
        print("Total coordinate points: \(allCoords.count)")
        
        // Center calculation
        let center = field.centerCoordinate
        print("Center: \(center.latitude), \(center.longitude)")
        
        // Polygon-specific analysis
        if let polygonCoords = field.polygonCoordinates {
            print("Polygon boundary points: \(polygonCoords.count)")
            
            // Check if a point is inside
            let testPoint = CLLocationCoordinate2D(latitude: 40.05, longitude: -95.45)
            let isInside = field.contains(coordinate: testPoint)
            print("Test point (\(testPoint.latitude), \(testPoint.longitude)) is \(isInside ? "inside" : "outside") the field")
            
            // Get approximate area
            let approxArea = field.approximateAreaHectares
            print("Approximate calculated area: \(String(format: "%.1f", approxArea)) ha")
        }
        
        // Geometry type specific handling
        switch field.geometry {
        case .polygon(let polygon):
            print("Polygon details:")
            print("- Outer ring points: \(polygon.outerRing.count)")
            print("- Number of holes: \(polygon.holes.count)")
            
        case .point(let point):
            print("Point location: \(point.coordinates.latitude), \(point.coordinates.longitude)")
            
        case .multiPolygon(let multiPolygon):
            print("MultiPolygon with \(multiPolygon.polygons.count) separate polygons")
            
        case .lineString(let lineString):
            print("LineString with \(lineString.coordinates.count) points")
            
        case .multiPoint(let multiPoint):
            print("MultiPoint with \(multiPoint.coordinates.count) points")
            
        case .multiLineString(let multiLineString):
            print("MultiLineString with \(multiLineString.coordinates.count) lines")
            
        case .geometryCollection(let collection):
            print("GeometryCollection with \(collection.geometries.count) geometries")
        }
    }
    
    /// Demonstrate field geometry updates
    static func updateFieldGeometry() {
        let field = createPointField()
        print("Original field has \(field.coordinates.count) coordinate(s)")
        
        // Update to a polygon
        let newPolygon = Polygon(coordinates: [[
            Position(longitude: -95.1, latitude: 40.05),
            Position(longitude: -95.09, latitude: 40.05),
            Position(longitude: -95.09, latitude: 40.06),
            Position(longitude: -95.1, latitude: 40.06),
            Position(longitude: -95.1, latitude: 40.05)
        ]])
        let newGeometry = GeoJSONGeometry.polygon(newPolygon)
        
        let updatedField = field.withGeometry(newGeometry)
        print("Updated field has \(updatedField.coordinates.count) coordinate(s)")
        print("Field ID unchanged: \(updatedField.id == field.id)")
    }
    
    /// Demonstrate JSON serialization
    static func jsonSerializationExample() {
        let field = createSimplePolygonField()
        
        do {
            // Encode to JSON
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let jsonData = try encoder.encode(field)
            let jsonString = String(data: jsonData, encoding: .utf8) ?? "Failed to convert"
            
            print("=== Field JSON ===")
            print(jsonString)
            
            // Decode from JSON
            let decoder = JSONDecoder()
            let decodedField = try decoder.decode(Field.self, from: jsonData)
            
            print("\n=== Decoded Field ===")
            print("Successfully decoded field: \(decodedField.name)")
            print("Geometry type: \(type(of: decodedField.geometry))")
            print("Coordinates: \(decodedField.coordinates.count) points")
            
        } catch {
            print("JSON serialization error: \(error)")
        }
    }
    
    /// Create multiple fields and demonstrate collection operations
    static func createFieldCollection() -> [Field] {
        return [
            createPolygonField(),
            createSimplePolygonField(),
            createRectangularField(),
            createPointField(),
            createMultiPolygonField()
        ]
    }
    
    /// Analyze a collection of fields
    static func analyzeFieldCollection() {
        let fields = createFieldCollection()
        
        print("=== Field Collection Analysis ===")
        print("Total fields: \(fields.count)")
        
        // Group by crop type
        let cropGroups = Dictionary(grouping: fields, by: \.cropType)
        print("Crop types: \(cropGroups.keys.joined(separator: ", "))")
        
        // Calculate total area
        let totalArea = fields.compactMap(\.meta.areaHa).reduce(0.0, +)
        print("Total area: \(String(format: "%.1f", totalArea)) ha")
        
        // Find fields by geometry type
        let polygonFields = fields.filter { field in
            if case .polygon = field.geometry { return true }
            return false
        }
        print("Polygon fields: \(polygonFields.count)")
        
        let pointFields = fields.filter { field in
            if case .point = field.geometry { return true }
            return false
        }
        print("Point fields: \(pointFields.count)")
        
        // Find center of all fields
        let allCoordinates = fields.flatMap(\.coordinates)
        if !allCoordinates.isEmpty {
            let avgLat = allCoordinates.map(\.latitude).reduce(0, +) / Double(allCoordinates.count)
            let avgLon = allCoordinates.map(\.longitude).reduce(0, +) / Double(allCoordinates.count)
            print("Collection center: \(avgLat), \(avgLon)")
        }
    }
}
