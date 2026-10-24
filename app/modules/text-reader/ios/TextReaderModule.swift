import ExpoModulesCore
import UIKit
import Vision

/// Reads text lines from a photo with Apple's on-device Vision framework.
public class TextReaderModule: Module {
  public func definition() -> ModuleDefinition {
    Name("TextReader")

    AsyncFunction("recognize") { (uri: String, promise: Promise) in
      guard let url = URL(string: uri),
            let data = try? Data(contentsOf: url),
            let image = UIImage(data: data),
            let cgImage = image.cgImage else {
        promise.reject("E_IMAGE", "Couldn't read the photo")
        return
      }
      let request = VNRecognizeTextRequest { request, error in
        if let error = error {
          promise.reject("E_OCR", error.localizedDescription)
          return
        }
        let lines = (request.results as? [VNRecognizedTextObservation])?
          .compactMap { $0.topCandidates(1).first?.string } ?? []
        promise.resolve(lines)
      }
      request.recognitionLevel = .accurate
      request.usesLanguageCorrection = false
      let handler = VNImageRequestHandler(cgImage: cgImage, orientation: Self.orientation(image.imageOrientation))
      DispatchQueue.global(qos: .userInitiated).async {
        do {
          try handler.perform([request])
        } catch {
          promise.reject("E_OCR", error.localizedDescription)
        }
      }
    }
  }

  private static func orientation(_ o: UIImage.Orientation) -> CGImagePropertyOrientation {
    switch o {
    case .up: return .up
    case .down: return .down
    case .left: return .left
    case .right: return .right
    case .upMirrored: return .upMirrored
    case .downMirrored: return .downMirrored
    case .leftMirrored: return .leftMirrored
    case .rightMirrored: return .rightMirrored
    @unknown default: return .up
    }
  }
}
