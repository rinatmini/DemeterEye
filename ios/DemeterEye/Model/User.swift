//
//  User.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import Foundation

struct User: Codable {
    let id: String
    let username: String
    let email: String
    
    // Parameter-based initializer
    init(id: String, username: String, email: String) {
        self.id = id
        self.username = username
        self.email = email
    }
    
    // Dictionary-based initializer
    init(from dictionary: [String: Any]) throws {
        guard let id = dictionary["id"] as? String,
              let username = dictionary["username"] as? String,
              let email = dictionary["email"] as? String else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Missing required fields in User dictionary")
            )
        }
        
        self.id = id
        self.username = username
        self.email = email
    }
}

struct AuthRequest: Codable {
    let email: String
    let password: String
}

struct RegisterRequest: Codable {
    let username: String
    let email: String
    let password: String
}

struct AuthResponse: Codable {
    let token: String
    
    // Parameter-based initializer
    init(token: String) {
        self.token = token
    }
    
    // Dictionary-based initializer
    init(from dictionary: [String: Any]) throws {
        guard let token = dictionary["token"] as? String else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Missing token in AuthResponse dictionary")
            )
        }
        
        self.token = token
    }
}
