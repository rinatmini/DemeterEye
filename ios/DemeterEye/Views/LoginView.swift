//
//  LoginView.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import SwiftUI
import Observation

struct LoginView: View {
    @State private var viewModel = LoginViewModel()
    @EnvironmentObject private var demeterService: DemeterService
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 40) {
                    // Header with branding
                    VStack(spacing: 16) {
                        Image(systemName: "eye.trianglebadge.exclamationmark")
                            .font(.system(size: 60))
                            .foregroundColor(.demeterGreen)
                        
                        Text("DemeterEye")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .foregroundColor(.primary)
                        
                        Text("Monitor Your Fields")
                            .font(.headline)
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 60)
                    
                    // Login Form
                    VStack(spacing: 20) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Email")
                                .font(.headline)
                                .foregroundColor(.primary)
                            
                            TextField("Enter your email", text: $viewModel.email)
                                .textFieldStyle(DemeterTextFieldStyle())
                                .textInputAutocapitalization(.never)
                                .keyboardType(.emailAddress)
                        }
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Password")
                                .font(.headline)
                                .foregroundColor(.primary)
                            
                            SecureField("Enter your password", text: $viewModel.password)
                                .textFieldStyle(DemeterTextFieldStyle())
                        }
                        
                        // Demo mode toggle
                        HStack {
                            Toggle("Demo Mode", isOn: $demeterService.isDemoMode)
                                .toggleStyle(SwitchToggleStyle())
                            Spacer()
                        }
                        .padding(.horizontal, 4)
                        
                        if demeterService.isDemoMode {
                            Text("Demo mode: Use any email/password to login")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .padding(.horizontal)
                        }
                        
                        if let errorMessage = viewModel.errorMessage {
                            Text(errorMessage)
                                .foregroundColor(.red)
                                .font(.body)
                                .padding(.horizontal)
                        }
                        
                        Button(action: {
                            Task {
                                await viewModel.login(using: demeterService)
                            }
                        }) {
                            HStack {
                                if viewModel.isLoading {
                                    ProgressView()
                                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                        .scaleEffect(0.8)
                                } else {
                                    Text("Log In")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                }
                            }
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 56)
                            .background(Color.demeterGreen)
                            .cornerRadius(12)
                        }
                        .disabled(viewModel.isLoading || !viewModel.isFormValid(demoMode: demeterService.isDemoMode))
                        .opacity(viewModel.isFormValid(demoMode: demeterService.isDemoMode) ? 1.0 : 0.6)
                    }
                    .padding(.horizontal, 24)
                    
                    Spacer()
                }
                .frame(minHeight: geometry.size.height)
            }
        }
        .background(Color.demeterBackground)
    }
}

@Observable
class LoginViewModel {
    var email = "nick2@example.com"
    var password = "pass123"
    var isLoading = false
    var errorMessage: String?
    
    func isFormValid(demoMode: Bool) -> Bool {
        if demoMode {
            return !email.isEmpty && !password.isEmpty
        }
        return !email.isEmpty && !password.isEmpty && email.contains("@")
    }
    
    func login(using service: DemeterService) async {
        isLoading = true
        errorMessage = nil
        
        do {
            try await service.login(email: email, password: password)
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
}

#Preview {
    LoginView()
        .environmentObject(DemeterService.shared)
}
