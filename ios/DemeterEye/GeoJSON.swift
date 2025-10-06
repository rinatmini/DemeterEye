//
//  GeoJSON.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation
import CoreLocation

// MARK: - GeoJSON Types

/// Represents a GeoJSON geometry object
public enum GeoJSONGeometry: Codable, Equatable {
    case point(Point)
    case multiPoint(MultiPoint)
    case lineString(LineString)
    case multiLineString(MultiLineString)
    case polygon(Polygon)
    case multiPolygon(MultiPolygon)
    case geometryCollection(GeometryCollection)
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)
        
        switch type {
        case "Point":
            let point = try Point(from: decoder)
            self = .point(point)
        case "MultiPoint":
            let multiPoint = try MultiPoint(from: decoder)
            self = .multiPoint(multiPoint)
        case "LineString":
            let lineString = try LineString(from: decoder)
            self = .lineString(lineString)
        case "MultiLineString":
            let multiLineString = try MultiLineString(from: decoder)
            self = .multiLineString(multiLineString)
        case "Polygon":
            let polygon = try Polygon(from: decoder)
            self = .polygon(polygon)
        case "MultiPolygon":
            let multiPolygon = try MultiPolygon(from: decoder)
            self = .multiPolygon(multiPolygon)
        case "GeometryCollection":
            let collection = try GeometryCollection(from: decoder)
            self = .geometryCollection(collection)
        default:
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unknown geometry type: \(type)")
            )
        }
    }
    
    public func encode(to encoder: Encoder) throws {
        switch self {
        case .point(let point):
            try point.encode(to: encoder)
        case .multiPoint(let multiPoint):
            try multiPoint.encode(to: encoder)
        case .lineString(let lineString):
            try lineString.encode(to: encoder)
        case .multiLineString(let multiLineString):
            try multiLineString.encode(to: encoder)
        case .polygon(let polygon):
            try polygon.encode(to: encoder)
        case .multiPolygon(let multiPolygon):
            try multiPolygon.encode(to: encoder)
        case .geometryCollection(let collection):
            try collection.encode(to: encoder)
        }
    }
    
    private enum CodingKeys: String, CodingKey {
        case type
    }
}

// MARK: - Position

/// A GeoJSON position (longitude, latitude, optional elevation)
public struct Position: Codable, Equatable {
    public let longitude: Double
    public let latitude: Double
    public let elevation: Double?
    
    public init(longitude: Double, latitude: Double, elevation: Double? = nil) {
        self.longitude = longitude
        self.latitude = latitude
        self.elevation = elevation
    }
    
    public init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        longitude = try container.decode(Double.self)
        latitude = try container.decode(Double.self)
        elevation = try? container.decode(Double.self)
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.unkeyedContainer()
        try container.encode(longitude)
        try container.encode(latitude)
        if let elevation = elevation {
            try container.encode(elevation)
        }
    }
    
    /// Convert to CLLocationCoordinate2D
    public var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }
}

// MARK: - Geometry Types

public struct Point: Codable, Equatable {
    public let type = "Point"
    public let coordinates: Position
    
    public init(coordinates: Position) {
        self.coordinates = coordinates
    }
    
    public init(longitude: Double, latitude: Double, elevation: Double? = nil) {
        self.coordinates = Position(longitude: longitude, latitude: latitude, elevation: elevation)
    }
}

public struct MultiPoint: Codable, Equatable {
    public let type = "MultiPoint"
    public let coordinates: [Position]
    
    public init(coordinates: [Position]) {
        self.coordinates = coordinates
    }
}

public struct LineString: Codable, Equatable {
    public let type = "LineString"
    public let coordinates: [Position]
    
    public init(coordinates: [Position]) {
        self.coordinates = coordinates
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let coordinateArrays = try container.decode([[Double]].self, forKey: .coordinates)
        coordinates = try coordinateArrays.map { coordArray in
            guard coordArray.count >= 2 else {
                throw DecodingError.dataCorrupted(
                    DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Position must have at least 2 coordinates")
                )
            }
            return Position(longitude: coordArray[0], latitude: coordArray[1], elevation: coordArray.count > 2 ? coordArray[2] : nil)
        }
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, coordinates
    }
}

public struct MultiLineString: Codable, Equatable {
    public let type = "MultiLineString"
    public let coordinates: [[Position]]
    
    public init(coordinates: [[Position]]) {
        self.coordinates = coordinates
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let coordinateArrays = try container.decode([[[Double]]].self, forKey: .coordinates)
        coordinates = try coordinateArrays.map { lineArray in
            try lineArray.map { coordArray in
                guard coordArray.count >= 2 else {
                    throw DecodingError.dataCorrupted(
                        DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Position must have at least 2 coordinates")
                    )
                }
                return Position(longitude: coordArray[0], latitude: coordArray[1], elevation: coordArray.count > 2 ? coordArray[2] : nil)
            }
        }
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, coordinates
    }
}

public struct Polygon: Codable, Equatable {
    public let type = "Polygon"
    public let coordinates: [[Position]]
    
    public init(coordinates: [[Position]]) {
        self.coordinates = coordinates
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let coordinateArrays = try container.decode([[[Double]]].self, forKey: .coordinates)
        coordinates = try coordinateArrays.map { ringArray in
            try ringArray.map { coordArray in
                guard coordArray.count >= 2 else {
                    throw DecodingError.dataCorrupted(
                        DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Position must have at least 2 coordinates")
                    )
                }
                return Position(longitude: coordArray[0], latitude: coordArray[1], elevation: coordArray.count > 2 ? coordArray[2] : nil)
            }
        }
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, coordinates
    }
    
    /// Get the outer ring (first ring) of the polygon
    public var outerRing: [Position] {
        coordinates.first ?? []
    }
    
    /// Get the holes (inner rings) of the polygon
    public var holes: [[Position]] {
        Array(coordinates.dropFirst())
    }
    
    /// Convert outer ring to CLLocationCoordinate2D array
    public var outerRingCoordinates: [CLLocationCoordinate2D] {
        outerRing.map(\.coordinate)
    }
}

public struct MultiPolygon: Codable, Equatable {
    public let type = "MultiPolygon"
    public let coordinates: [[[Position]]]
    
    public init(coordinates: [[[Position]]]) {
        self.coordinates = coordinates
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let coordinateArrays = try container.decode([[[[Double]]]].self, forKey: .coordinates)
        coordinates = try coordinateArrays.map { polygonArray in
            try polygonArray.map { ringArray in
                try ringArray.map { coordArray in
                    guard coordArray.count >= 2 else {
                        throw DecodingError.dataCorrupted(
                            DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Position must have at least 2 coordinates")
                        )
                    }
                    return Position(longitude: coordArray[0], latitude: coordArray[1], elevation: coordArray.count > 2 ? coordArray[2] : nil)
                }
            }
        }
    }
    
    private enum CodingKeys: String, CodingKey {
        case type, coordinates
    }
    
    /// Convert to array of Polygon objects
    public var polygons: [Polygon] {
        coordinates.map { Polygon(coordinates: $0) }
    }
}

public struct GeometryCollection: Codable, Equatable {
    public let type = "GeometryCollection"
    public let geometries: [GeoJSONGeometry]
    
    public init(geometries: [GeoJSONGeometry]) {
        self.geometries = geometries
    }
}

// MARK: - GeoJSON Extensions

extension GeoJSONGeometry {
    /// Extract all positions from any geometry type
    public var allPositions: [Position] {
        switch self {
        case .point(let point):
            return [point.coordinates]
        case .multiPoint(let multiPoint):
            return multiPoint.coordinates
        case .lineString(let lineString):
            return lineString.coordinates
        case .multiLineString(let multiLineString):
            return multiLineString.coordinates.flatMap { $0 }
        case .polygon(let polygon):
            return polygon.coordinates.flatMap { $0 }
        case .multiPolygon(let multiPolygon):
            return multiPolygon.coordinates.flatMap { $0.flatMap { $0 } }
        case .geometryCollection(let collection):
            return collection.geometries.flatMap { $0.allPositions }
        }
    }
    
    /// Calculate the center coordinate of the geometry
    public var centerCoordinate: CLLocationCoordinate2D {
        let positions = allPositions
        guard !positions.isEmpty else {
            return CLLocationCoordinate2D(latitude: 0, longitude: 0)
        }
        
        let avgLat = positions.map(\.latitude).reduce(0, +) / Double(positions.count)
        let avgLon = positions.map(\.longitude).reduce(0, +) / Double(positions.count)
        
        return CLLocationCoordinate2D(latitude: avgLat, longitude: avgLon)
    }
    
    /// Convert all positions to CLLocationCoordinate2D array
    public var allCoordinates: [CLLocationCoordinate2D] {
        allPositions.map(\.coordinate)
    }
}
