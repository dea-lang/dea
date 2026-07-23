import XCTest
import SwiftTreeSitter
import TreeSitterDea

final class TreeSitterDeaTests: XCTestCase {
    func testCanLoadGrammar() throws {
        let parser = Parser()
        let language = Language(language: tree_sitter_dea())
        XCTAssertNoThrow(try parser.setLanguage(language),
                         "Error loading Dea grammar")
    }
}
