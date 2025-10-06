//
//  DemeterDesignSystem.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import SwiftUI

// MARK: - Colors
extension Color {
    static let demeterGreen = Color(red: 0.2, green: 0.6, blue: 0.2)
    static let demeterBrown = Color(red: 0.6, green: 0.4, blue: 0.2)
    static let demeterBeige = Color(red: 0.96, green: 0.94, blue: 0.9)
    static let demeterBackground = Color(red: 0.98, green: 0.98, blue: 0.96)
}

// MARK: - Text Field Style
struct DemeterTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .padding(.horizontal, 16)
            .padding(.vertical, 16)
            .background(Color.white)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.gray.opacity(0.3), lineWidth: 1)
            )
            .font(.body)
    }
}

// MARK: - Button Styles
struct DemeterButtonStyle: ButtonStyle {
    let backgroundColor: Color
    let foregroundColor: Color
    
    init(backgroundColor: Color = .demeterGreen, foregroundColor: Color = .white) {
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor
    }
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundColor(foregroundColor)
            .frame(maxWidth: .infinity)
            .frame(height: 56)
            .background(backgroundColor)
            .cornerRadius(12)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.1), value: configuration.isPressed)
    }
}