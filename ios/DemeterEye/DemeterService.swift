//
//  DemeterService.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation
import Combine

@MainActor
class DemeterService: ObservableObject {
    static let shared = DemeterService()
    
    private let baseURL = "https://demetereye-api-1060536779509.us-central1.run.app/api"
    private let session = URLSession.shared
    
    // Demo mode for testing without API
    var isDemoMode = false
    
    @Published var isAuthenticated = false
    
    private var authToken: String? {
        get { UserDefaults.standard.string(forKey: "auth_token") }
        set {
            UserDefaults.standard.set(newValue, forKey: "auth_token")
            isAuthenticated = newValue != nil
        }
    }
    
    private init() {
        // Check if user is already authenticated
        if authToken != nil {
            isAuthenticated = true
        }
    }
    
    // MARK: - Authentication
    
    func login(email: String, password: String) async throws {
        if isDemoMode {
            // Demo mode - simulate successful login
            try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second delay
            isAuthenticated = true
            return
        }
        
        // For demo purposes, we'll use the register endpoint
        // In production, you'd have a dedicated login endpoint
        let loginURL = URL(string: "\(baseURL)/auth/login")!
        var request = createRequest(url: loginURL, method: "POST")
        
        let authRequest = AuthRequest(email: email, password: password)
        let requestData = try JSONEncoder().encode(authRequest)
        
        request.httpBody = requestData
        
        // Log full request details
        print("Login Request URL: \(request.url?.absoluteString ?? "nil")")
        print("Login Request Method: \(request.httpMethod ?? "nil")")
        print("Login Request Headers: \(request.allHTTPHeaderFields ?? [:])")
        if let jsonString = String(data: requestData, encoding: .utf8) {
            print("Login Request Data: \(jsonString)")
        }
        print("Login Request Size: \(requestData.count) bytes")
        
        do {
            let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw DemeterError.networkError
            }
            
            // Handle both 200 and 201 status codes for flexibility
            guard httpResponse.statusCode == 200 || httpResponse.statusCode == 201 else {
                throw DemeterError.authenticationFailed
            }
            
            let authResponse = try AuthResponse(from: try parseJsonToDictionary(from: data))
            authToken = authResponse.token
        } catch is DecodingError {
            throw DemeterError.authenticationFailed
        } catch {
            throw DemeterError.networkError
        }
    }
    
    func register(username: String, email: String, password: String) async throws {
        let registerURL = URL(string: "\(baseURL)/auth/register")!
        var request = createRequest(url: registerURL, method: "POST")
        
        let registerRequest = RegisterRequest(username: username, email: email, password: password)
        let requestData = try JSONEncoder().encode(registerRequest)
        
        request.httpBody = requestData
        
        // Log full request details
        print("Register Request URL: \(request.url?.absoluteString ?? "nil")")
        print("Register Request Method: \(request.httpMethod ?? "nil")")
        print("Register Request Headers: \(request.allHTTPHeaderFields ?? [:])")
        if let jsonString = String(data: requestData, encoding: .utf8) {
            print("Register Request Data: \(jsonString)")
        }
        print("Register Request Size: \(requestData.count) bytes")
        
        do {
            let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw DemeterError.networkError
            }
            
            guard httpResponse.statusCode == 201 || httpResponse.statusCode == 200 else {
                throw DemeterError.registrationFailed
            }
            
            let authResponse = try AuthResponse(from: try parseJsonToDictionary(from: data))
            authToken = authResponse.token
        } catch is DecodingError {
            throw DemeterError.registrationFailed
        } catch {
            throw DemeterError.networkError
        }
    }
    
    func logout() {
        authToken = nil
    }
    
    // MARK: - Fields API
    
    func fetchFields() async throws -> [Field] {
        if isDemoMode {
            // Demo mode - return mock data
            try await Task.sleep(nanoseconds: 500_000_000) // 0.5 second delay
            return Field.mockFields
        }
        
        guard let token = authToken else {
            throw DemeterError.notAuthenticated
        }
        
        let fieldsURL = URL(string: "\(baseURL)/fields")!
        var request = createRequest(url: fieldsURL, method: "GET")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        do {
            let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw DemeterError.networkError
            }
            
            guard httpResponse.statusCode == 200 else {
                if httpResponse.statusCode == 401 {
                    // Token expired, logout user
                    logout()
                    throw DemeterError.notAuthenticated
                }
                throw DemeterError.fetchFieldsFailed
            }
            
            return try parseJsonToArray(from: data).map { try Field(from: $0) }
        } catch let error as DecodingError {
            throw DemeterError.fetchFieldsFailed
        } catch {
            throw DemeterError.networkError
        }
    }
    
    // MARK: - Helper Methods
    
    private func createRequest(url: URL, method: String) -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return request
    }
    
    private func parseJsonToDictionary(from data: Data) throws -> [String: Any] {
        guard let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Invalid JSON format - expected dictionary")
            )
        }
        return json
    }
    
    private func parseJsonToArray(from data: Data) throws -> [[String: Any]] {
        guard let json = try JSONSerialization.jsonObject(with: data, options: []) as? [[String: Any]] else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Invalid JSON format - expected array of dictionaries")
            )
        }
        return json
    }
}

enum DemeterError: Error, LocalizedError {
    case notAuthenticated
    case authenticationFailed
    case registrationFailed
    case fetchFieldsFailed
    case networkError
    
    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Not authenticated"
        case .authenticationFailed:
            return "Login failed. Please check your credentials."
        case .registrationFailed:
            return "Registration failed. Please try again."
        case .fetchFieldsFailed:
            return "Failed to fetch fields"
        case .networkError:
            return "Network error occurred"
        }
    }
}
