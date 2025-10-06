//
//  ContentView.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var demeterService = DemeterService.shared
    
    var body: some View {
        Group {
            if demeterService.isAuthenticated {
                FieldsListView()
                    .environmentObject(demeterService)
            } else {
                LoginView()
                    .environmentObject(demeterService)
            }
        }
    }
}

#Preview {
    ContentView()
}
