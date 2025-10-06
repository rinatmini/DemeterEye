//
//  FieldsListView.swift
//  DemeterEye
//
//  Created by Konstantin Polin on 10/2/25.
//

import SwiftUI
import MapKit
import Observation

struct FieldsListView: View {
    @State private var viewModel = FieldsListViewModel()
    @EnvironmentObject private var demeterService: DemeterService
    
    var body: some View {
        NavigationStack {
            ZStack {
                if viewModel.isLoading && viewModel.fields.isEmpty {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.2)
                        Text("Loading your fields...")
                            .foregroundColor(.secondary)
                    }
                } else if viewModel.fields.isEmpty && !viewModel.isLoading {
                    VStack(spacing: 16) {
                        Image(systemName: "map")
                            .font(.system(size: 60))
                            .foregroundColor(.secondary)
                        
                        Text("No Fields Found")
                            .font(.title2)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                        
                        Text("Add fields to start monitoring your crops")
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    ScrollView {
                        LazyVStack(spacing: 16) {
                            ForEach(viewModel.fields) { field in
                                NavigationLink {
                                    FieldDetailView(field: field)
                                } label: {
                                    FieldRowView(field: field)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                    }
                }
            }
            .background(Color.demeterBackground)
            .navigationTitle("My Fields")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Logout") {
                        demeterService.logout()
                    }
                    .foregroundColor(.demeterGreen)
                }
            }
            .task {
                await viewModel.loadFields(using: demeterService)
            }
            .refreshable {
                await viewModel.loadFields(using: demeterService)
            }
        }
    }
}

struct FieldRowView: View {
    let field: Field
    
    var body: some View {
        HStack(spacing: 16) {
            // Thumbnail map
            Map(initialPosition: .region(
                MKCoordinateRegion(
                    center: field.centerCoordinate,
                    span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                )
            )) {
                MapPolygon(coordinates: field.coordinates)
                    .foregroundStyle(Color.demeterGreen.opacity(0.3))
                    .stroke(Color.demeterGreen, lineWidth: 2)
            }
            .frame(width: 80, height: 80)
            .cornerRadius(12)
            .allowsHitTesting(false)
            
            // Field information
            VStack(alignment: .leading, spacing: 8) {
                Text(field.name)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                
                HStack(spacing: 4) {
                    Image(systemName: "leaf.fill")
                        .foregroundColor(.demeterGreen)
                        .font(.caption)
                    
                    Text(field.cropType)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                HStack(spacing: 4) {
                    Image(systemName: "map")
                        .foregroundColor(.secondary)
                        .font(.caption)
                    
                    Text(field.areaText)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
                .font(.caption)
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.05), radius: 8, x: 0, y: 2)
    }
}

@Observable
class FieldsListViewModel {
    var fields: [Field] = []
    var isLoading = false
    var errorMessage: String?
    
    func loadFields(using service: DemeterService) async {
        isLoading = true
        errorMessage = nil
        
        do {
            fields = try await service.fetchFields()
        } catch {
            errorMessage = error.localizedDescription
            fields = []
        }
        
        isLoading = false
    }
}

#Preview {
    FieldsListView()
        .environmentObject(DemeterService.shared)
}

