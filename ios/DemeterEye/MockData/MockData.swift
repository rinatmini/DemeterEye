//
//  MockData.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation

extension Field {
    static let mockFields: [Field] = [
        Field(
            id: "mock1",
            ownerId: "owner1",
            name: "North Field A",
            geometry: GeoJSONGeometry.polygon(Polygon(coordinates: [
                [
                    Position(longitude: 36.121, latitude: 49.987),
                    Position(longitude: 36.128, latitude: 49.988),
                    Position(longitude: 36.127, latitude: 49.992),
                    Position(longitude: 36.120, latitude: 49.991),
                    Position(longitude: 36.121, latitude: 49.987)
                ]
            ])),
            createdAt: "2025-10-01T20:30:00Z",
            meta: FieldMeta(areaHa: 12.8, notes: "Sunny side; loam soil", crop: "wheat"),
            history: [
                FieldHistory(
                    date: "2024-03-25T00:00:00Z",
                    ndvi: 0.28,
                    cloudCover: 6,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 9.1,
                    humidityPct: 68.0,
                    cloudcoverPct: 34.0,
                    windSpeedMps: 3.4,
                    clarityPct: 66.0
                ),
                FieldHistory(
                    date: "2024-05-18T00:00:00Z",
                    ndvi: 0.78,
                    cloudCover: 2,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 18.9,
                    humidityPct: 55.0,
                    cloudcoverPct: 8.0,
                    windSpeedMps: 2.1,
                    clarityPct: 92.0
                ),
                FieldHistory(
                    date: "2024-08-20T00:00:00Z",
                    ndvi: 0.45,
                    cloudCover: 5,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 22.5,
                    humidityPct: 62.0,
                    cloudcoverPct: 18.0,
                    windSpeedMps: 2.8,
                    clarityPct: 82.0
                )
            ],
            forecast: ForecastData(
                year: 2025,
                yieldTph: 4.5,
                ndviPeak: 0.73,
                ndviPeakAt: "2025-05-22T00:00:00Z",
                yieldModel: "xgb-v1",
                yieldConfidence: 0.72,
                updatedAt: "2025-10-01T20:31:00Z"
            )
        ),
        Field(
            id: "mock2",
            ownerId: "owner1",
            name: "South Field B",
            geometry: GeoJSONGeometry.polygon(Polygon(coordinates: [
                [
                    Position(longitude: 36.130, latitude: 49.980),
                    Position(longitude: 36.137, latitude: 49.981),
                    Position(longitude: 36.136, latitude: 49.985),
                    Position(longitude: 36.129, latitude: 49.984),
                    Position(longitude: 36.130, latitude: 49.980)
                ]
            ])),
            createdAt: "2025-09-15T18:45:00Z",
            meta: FieldMeta(areaHa: 18.5, notes: "Clay soil, good drainage", crop: "corn"),
            history: [
                FieldHistory(
                    date: "2024-04-10T00:00:00Z",
                    ndvi: 0.35,
                    cloudCover: 4,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 11.2,
                    humidityPct: 63.4,
                    cloudcoverPct: 18.5,
                    windSpeedMps: 2.8,
                    clarityPct: 81.5
                ),
                FieldHistory(
                    date: "2024-06-25T00:00:00Z",
                    ndvi: 0.82,
                    cloudCover: 1,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 25.1,
                    humidityPct: 50.8,
                    cloudcoverPct: 6.0,
                    windSpeedMps: 2.3,
                    clarityPct: 94.0
                ),
                FieldHistory(
                    date: "2024-09-15T00:00:00Z",
                    ndvi: 0.58,
                    cloudCover: 7,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 18.7,
                    humidityPct: 65.2,
                    cloudcoverPct: 25.1,
                    windSpeedMps: 3.6,
                    clarityPct: 74.9
                )
            ],
            forecast: ForecastData(
                year: 2025,
                yieldTph: 9.2,
                ndviPeak: 0.79,
                ndviPeakAt: "2025-06-20T00:00:00Z",
                yieldModel: "xgb-v1",
                yieldConfidence: 0.78,
                updatedAt: "2025-10-01T20:31:00Z"
            )
        ),
        Field(
            id: "mock3",
            ownerId: "owner1",
            name: "East Pasture",
            geometry: GeoJSONGeometry.polygon(Polygon(coordinates: [
                [
                    Position(longitude: 36.140, latitude: 49.995),
                    Position(longitude: 36.148, latitude: 49.996),
                    Position(longitude: 36.147, latitude: 50.001),
                    Position(longitude: 36.139, latitude: 50.000),
                    Position(longitude: 36.140, latitude: 49.995)
                ]
            ])),
            createdAt: "2025-08-20T14:20:00Z",
            meta: FieldMeta(areaHa: 25.3, notes: "Mixed soil types, rolling hills", crop: "soybeans"),
            history: [
                FieldHistory(
                    date: "2024-05-05T00:00:00Z",
                    ndvi: 0.42,
                    cloudCover: 8,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 15.3,
                    humidityPct: 60.6,
                    cloudcoverPct: 24.3,
                    windSpeedMps: 3.5,
                    clarityPct: 75.7
                ),
                FieldHistory(
                    date: "2024-07-12T00:00:00Z",
                    ndvi: 0.74,
                    cloudCover: 3,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 26.4,
                    humidityPct: 48.1,
                    cloudcoverPct: 12.0,
                    windSpeedMps: 2.9,
                    clarityPct: 88.0
                ),
                FieldHistory(
                    date: "2024-09-28T00:00:00Z",
                    ndvi: 0.51,
                    cloudCover: 9,
                    collection: "HLSS30_2.0",
                    temperatureDegC: 19.8,
                    humidityPct: 58.7,
                    cloudcoverPct: 31.2,
                    windSpeedMps: 4.1,
                    clarityPct: 68.8
                )
            ],
            forecast: ForecastData(
                year: 2025,
                yieldTph: 3.6,
                ndviPeak: 0.76,
                ndviPeakAt: "2025-07-15T00:00:00Z",
                yieldModel: "xgb-v1",
                yieldConfidence: 0.69,
                updatedAt: "2025-10-01T20:31:00Z"
            )
        )
    ]
}
